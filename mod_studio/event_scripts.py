"""
Event scripts: the scenes and battle events of The Ivalice Chronicles, read,
grouped into nodes, played out frame by frame, and written back.

Zodi's Task 4 (12 October): "a node based Event Editor with a map viewer to
preview the events, and it should have the feature to play each node
forward or backward"; Nenkai's notes: "The game itself overrides
fftpack/event_test_evt to load from the script/ folder instead. Use this
folder instead to mod scripts!" Approved by name on 19 October ("Yes, make
all three": this module, `state.script_edits`, new lines in a scene's text).

**Where they are.** `script/enhanced/eventNNN.e` (560 files: 000 to 491, 590
to 595, 750 to 882) and `script/classic/eventNNN.e` (493, with
`tutobtlNN.e` and the 14 `tutoeditNN.<lang>.e`, which are another format).
The game reads an event as 5 sectors in Enhanced and 3 in Classic (the mod
loader's `FFTPackHooks.cs`), and a mod replaces one by shipping it at the
same path under `FFTIVC/data/<mode>/`, as WotL Restoration ships 512 to 581.

**The format**, measured on all of them. A stream of instructions: an
opcode byte, then as many operand bytes as the opcode's length says;
16-bit values little endian and unaligned. No header, no text inside.

- **Classic lengths** are the PlayStation's: the 244 lengths in BATTLE.BIN
  at file offset `0xE6170` (the game's `fftpack/battle_bin.en.bin`, byte
  for byte the US PlayStation file). They are read from the game, never
  copied here.
- **Enhanced lengths** are those with three changes: DisplayMessage (`10`)
  17 operand bytes, its text id 32 bits (14 on the PlayStation),
  ChangeDialog (`51`) 7 (5), and 32 opcodes the PlayStation hasn't
  (`NEW_LENGTHS`), which Classic accepts too (event300 has an `EC`).
- **The end**: an `END` (`DB`) once no forward jump (`D0`, `D1`) still
  waits for its target (`D2`, `D4`). What follows is kept as it is
  (`Script.tail`): 4 bytes in 373 enhanced files (the first 4 bytes of the
  PlayStation text, left by the conversion), a PlayStation block of old
  code and text in 26, and 161 files are a placeholder of three
  instructions (`4D 02`, `F1 1E 00`, `DB`) padded to 6,140 bytes. WotL's
  files end at their `DB`, and the game plays them.
- **Measured**: every one of the game's 560 enhanced scripts (399 real, 161
  placeholders) and WotL's 70 reads to its end and back byte for byte; so
  do the 501 classic events and tutorial battles (340 real). An opcode no
  interpreter handles ends a script in the game (the PlayStation
  decompilation's notes); none is met before an end in any of them, and
  one that is ends the reading too (`Script.stopped`).

**What each instruction means** comes from the PlayStation decompilation
(adamrt's `fft_decomp`, `include/fft/script_instruction.h` and the
interpreter; it has no licence file, so it is read for facts and nothing
is copied) and the FFHacktics wiki, checked on the game's own scripts:
which operand is which, and what a value does. The remaster's new opcodes
are mostly unknown and are shown as their numbers; a few were worked out
from their uses (`EB` turns a speech box to its next page, naming the line
and the next; `C2` names a line by its 32-bit id).

**Time.** An instruction takes no time; the waits do (`WAIT`'s frames, the
waits for a message, a camera, a walk or a turn to finish). A frame is a
60th of a second (`FRAMES_A_SECOND`): the decompilation's tutorial divides
a Wait by the frame interval to keep it in vertical blanks, and a walk's
speed is scaled by the interval so it moves the same in real time at
either rate. That is the PlayStation's; the remaster's is not measured. A
message waits for a button: the preview gives the reader time for the words
(`button_frames`).

**Which map and units.** The map and ENTD battle an event uses are in the
game's program (the event setup record), which Mod Studio can't read; for
the PlayStation's events (1 to 490) the scenario table the game keeps
(`battle_maps.read_scenarios`) names them. The units are the ENTD battle's
(`battle_units`: the four `battle_entd` files, or for 512 to 588 the fifth,
`event_btlevt_bin_entrydata_add_ent.bin`).

**The player's own units** (Zodi, 19 October: "for some special characters
and Ramza the player can choose where to place him at the map at the start
of the battle so they do appear, but according to the ENTD they are not
listed"). A story character the script names that neither the battle nor a
WarpUnit places is one the player deployed: it stands on the battle's
deployment tiles, Ramza first, as the game puts him on the first (the
decompilation's `attack_deployment_entrypoint`). The tiles are ATTACK.OUT's
squads (`deploy_squad_t`, `SQUADS_AT`): a scenario names one or two, each a
5 by 5 grid of tiles that may be used about a middle tile, turned as its
orientation byte says, measured to be on the scenario's own map in every
battle (`deployment`). With none (an event the scenario table hasn't), the
unit stands beside the first unit it speaks to. Unit ids 0x64 to 0x69 are
picked as the event runs (the unit taking its turn, say), so naming one is
no problem.

**The words** are lines of the scene's text file,
`nxd/text/scenario/scenarioNNNN.<lang>.pzd` (`ScenarioId` and `ScionFiles`
say which; `pzd_data` reads it): a DisplayMessage's text id is a line id.
A speaker's box is of kind 0x10 or 0x70 (`SPEECH_KINDS`): the dialog thread
makes a 0x70 a 0x10 at the top or bottom of the screen as its speaker faces
the camera (`facing_window`), as most boxes in battles are.

Nothing here imports Qt.
"""
from __future__ import annotations

import json
import re
import sqlite3
import struct
from collections import deque
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Callable, Optional

from . import battle_maps as bm
from . import entd

# =============================================================================
# Files
# =============================================================================

MODES = ("enhanced", "classic")
#: Where each mode keeps its scripts, under the unpacked game and under a
#: mod's `FFTIVC/data/<mode>/`.
SCRIPT_FOLDERS = {"enhanced": "script/enhanced", "classic": "script/classic"}
SCRIPT_NAME = re.compile(r"^event(\d{3})\.e$", re.IGNORECASE)
#: The PlayStation's BATTLE.BIN in the unpacked game, and where its 244
#: operand lengths are (RAM 0x8014D170; the file is loaded at 0x80067000).
BATTLE_BIN = "fftpack/battle_bin.en.bin"
LENGTHS_AT, LENGTH_COUNT = 0xE6170, 244
#: The two lengths the remaster changed (DisplayMessage, ChangeDialog).
ENHANCED_LENGTHS = {0x10: 17, 0x51: 7}
#: The remaster's opcodes the PlayStation hasn't, with their lengths:
#: measured by decoding every script, each checked by eye on its uses.
NEW_LENGTHS = {
    0xA6: 4, 0xA7: 4, 0xA8: 6, 0xA9: 6, 0xAA: 1, 0xAB: 4, 0xAC: 4, 0xAD: 8, 0xAE: 8, 0xAF: 4,
    0xC1: 0, 0xC2: 4, 0xC3: 0, 0xC4: 12, 0xC5: 8, 0xC6: 8, 0xC8: 8, 0xC9: 1, 0xCA: 1, 0xCB: 8,
    0xCC: 12, 0xCD: 8, 0xCE: 1, 0xCF: 0, 0xE7: 4, 0xE8: 1, 0xE9: 8, 0xEA: 5, 0xEB: 10, 0xEC: 0,
    0xED: 6, 0xEF: 0,
}
#: The opcodes the PlayStation's interpreter has a case for (the
#: decompilation's `event_opcode_e`, less those it calls unhandled): any
#: other byte ends a script there.
PLAYSTATION_OPCODES = frozenset(
    list(range(0x10, 0x14)) + [0x16, 0x17, 0x18, 0x19, 0x1A, 0x1B, 0x1C, 0x1D, 0x1E, 0x1F]
    + list(range(0x21, 0x2F)) + [0x31, 0x32, 0x33] + list(range(0x37, 0x52)) + list(range(0x53, 0x67))
    + list(range(0x68, 0x8D)) + list(range(0x8E, 0x9A)) + list(range(0xA0, 0xA6))
    + list(range(0xB0, 0xBF)) + [0xC0, 0xD0, 0xD1, 0xD2, 0xD3, 0xD4, 0xD5, 0xD8, 0xD9, 0xDA, 0xDB,
                                  0xDC, 0xE0, 0xE3, 0xE5, 0xF0, 0xF1, 0xF2])
HANDLED = PLAYSTATION_OPCODES | frozenset(NEW_LENGTHS)

END = 0xDB
FORWARD_JUMPS = (0xD0, 0xD1)
FORWARD_TARGETS = (0xD2, 0xD4)
#: How many bytes the game reads for an event (5 sectors of 2,048 in
#: Enhanced, 3 in Classic: the mod loader's notes). The largest of the
#: game's own is 6,149.
MOST_BYTES = {"enhanced": 5 * 2048, "classic": 3 * 2048}

#: A frame of an event, a 60th of a second (see the module's notes).
FRAMES_A_SECOND = 60


class ScriptError(ValueError):
    """A script, or the table its lengths come from, that can't be read."""


@dataclass(frozen=True)
class Lengths:
    """Each opcode's operand length in the two modes: 256 entries, 0 for none."""
    classic: tuple
    enhanced: tuple

    def of(self, mode: str) -> tuple:
        return self.enhanced if mode == "enhanced" else self.classic


def read_lengths(battle_bin: bytes) -> Lengths:
    """The two modes' lengths from the PlayStation's BATTLE.BIN."""
    table = bytes(battle_bin[LENGTHS_AT:LENGTHS_AT + LENGTH_COUNT])
    # The table's first known entries (DisplayMessage 14, UnitAnim 5, the
    # Camera's 16): a file without them isn't BATTLE.BIN, or is a stand-in
    # that kept other tables only.
    if len(table) < LENGTH_COUNT or (table[0x10], table[0x11], table[0x19]) != (14, 5, 16):
        raise ScriptError("BATTLE.BIN has no instruction length table where the PlayStation keeps it "
                          "(0xE6170)")
    classic = list(table) + [0] * (256 - LENGTH_COUNT)
    for opcode, length in NEW_LENGTHS.items():
        classic[opcode] = length
    enhanced = list(classic)
    for opcode, length in ENHANCED_LENGTHS.items():
        enhanced[opcode] = length
    return Lengths(tuple(classic), tuple(enhanced))


def lengths_from_game(game_dir) -> Lengths:
    """The lengths from an unpacked game's BATTLE.BIN; ScriptError says why not."""
    if not game_dir:
        raise ScriptError("no unpacked game")
    path = Path(game_dir) / BATTLE_BIN
    try:
        return read_lengths(path.read_bytes())
    except OSError:
        raise ScriptError(f"{BATTLE_BIN} isn't in the unpacked game") from None


def script_relative(number: int, mode: str = "enhanced") -> str:
    """`script/enhanced/event538.e`: where event `number` is, under the game and under a mod's data folder."""
    return f"{SCRIPT_FOLDERS[mode]}/event{int(number):03d}.e"


def script_number(relative: str) -> Optional[int]:
    """The event number of a script's path, or None for anything else."""
    match = SCRIPT_NAME.match(Path(str(relative).replace("\\", "/")).name)
    return int(match.group(1)) if match else None


def game_script_numbers(game_dir, mode: str = "enhanced") -> list:
    """The events the unpacked game has a script for, in number order."""
    folder = Path(game_dir) / SCRIPT_FOLDERS[mode] if game_dir else None
    if folder is None or not folder.is_dir():
        return []
    found = []
    for path in folder.iterdir():
        number = script_number(path.name)
        if number is not None and path.is_file():
            found.append(number)
    return sorted(found)


# =============================================================================
# Instructions
# =============================================================================

@dataclass(frozen=True)
class Instruction:
    opcode: int
    operands: bytes = b""

    def to_bytes(self) -> bytes:
        return bytes([self.opcode]) + bytes(self.operands)

    @property
    def size(self) -> int:
        return 1 + len(self.operands)


@dataclass
class Script:
    """A script's instructions up to its end, and the bytes after it, as they were."""
    mode: str
    instructions: list
    tail: bytes = b""
    #: Why reading stopped before an end ("" when it reached one).
    stopped: str = ""

    def to_bytes(self) -> bytes:
        return b"".join(i.to_bytes() for i in self.instructions) + bytes(self.tail)

    def code_size(self) -> int:
        return sum(i.size for i in self.instructions)

    def with_instructions(self, instructions) -> "Script":
        return Script(self.mode, list(instructions), self.tail, self.stopped)

    def is_placeholder(self) -> bool:
        """The game's 161 empty events: the map comes in, a wait, the end."""
        return [i.opcode for i in self.instructions] == [0x4D, 0xF1, END]


def read_script(data: bytes, lengths: Lengths, mode: str = "enhanced") -> Script:
    """
    `data` as a script: its instructions to its end and the bytes after.
    Raises ScriptError when the instructions run past the file's end (a
    script cut short, or a file that isn't one).
    """
    data = bytes(data)
    table = lengths.of(mode)
    out, at, waiting = [], 0, set()
    while at < len(data):
        opcode = data[at]
        if opcode not in HANDLED:
            return Script(mode, out, data[at:], f"an instruction no version of the game has ({opcode:02X}) "
                                                f"at byte {at}")
        end = at + 1 + table[opcode]
        if end > len(data):
            raise ScriptError(f"instruction {opcode:02X} at byte {at} runs past the end of the file")
        out.append(Instruction(opcode, data[at + 1:end]))
        if opcode in FORWARD_JUMPS:
            waiting.add(data[at + 1])
        elif opcode in FORWARD_TARGETS:
            waiting.discard(data[at + 1])
        at = end
        if opcode == END and not waiting:
            return Script(mode, out, data[at:])
    raise ScriptError("the script never ends: no END instruction after its last jump's target")


def write_script(script: Script) -> bytes:
    return script.to_bytes()


def ends_properly(script: Script, lengths: Lengths) -> bool:
    """Whether the script, written, reads back as itself: every jump's target there, an end last."""
    try:
        again = read_script(script.to_bytes(), lengths, script.mode)
    except ScriptError:
        return False
    return again.instructions == script.instructions and not again.stopped


# =============================================================================
# Operands
# =============================================================================

@dataclass(frozen=True)
class Operand:
    """One operand of an instruction: where it is in the operand bytes, how
    wide, signed or not, and what its number is (`kind`)."""
    name: str
    at: int
    size: int = 1
    signed: bool = False
    kind: str = "number"


def _ops(*specs) -> tuple:
    """Operands from `(name, size, signed, kind)`, laid one after another."""
    out, at = [], 0
    for name, size, signed, kind in specs:
        out.append(Operand(name, at, size, signed, kind))
        at += size
    return tuple(out)


U8, U16, S16, U32 = 1, 2, 2, 4
#: The operands of the instructions whose layout is known (the
#: decompilation's notes and structs, and the wiki's DisplayMessage page;
#: the remaster's DisplayMessage, ChangeDialog, EB and C2 measured).
LAYOUTS = {
    0x10: _ops(("thread", U8, False, "number"), ("box", U8, False, "box"), ("line", U16, False, "line"),
               ("unit", U16, False, "unit"), ("portrait", U8, False, "portrait"),
               ("dx", S16, True, "offset"), ("dy", S16, True, "offset"), ("arrow", S16, True, "offset"),
               ("options", U8, False, "number")),
    0x11: _ops(("unit", U16, False, "units"), ("animation", U16, False, "animation"),
               ("keep_facing", U8, False, "number")),
    0x12: _ops(("unit", U16, False, "unit")),
    0x13: _ops(("map", U16, False, "map")),
    0x18: _ops(("effect", U16, False, "effect"), ("target", U8, False, "unit"), ("x", U8, False, "x"),
               ("y", U8, False, "y"), ("target_mode", U8, False, "number")),
    0x19: _ops(("x", S16, True, "camera"), ("height", S16, True, "camera"), ("y", S16, True, "camera"),
               ("tilt", S16, True, "angle"), ("yaw", S16, True, "angle"), ("roll", S16, True, "angle"),
               ("zoom", S16, True, "zoom"), ("frames", S16, True, "frames")),
    0x1A: _ops(("style", U8, False, "number"), ("red", U8, True, "colour"), ("green", U8, True, "colour"),
               ("blue", U8, True, "colour"), ("frames", U8, False, "frames")),
    0x1B: _ops(("angle_x", S16, True, "number"), ("angle_y", S16, True, "number"),
               ("angle_z", S16, True, "number"), ("scale_x", S16, True, "number"),
               ("scale_y", S16, True, "number"), ("scale_z", S16, True, "number"),
               ("frames", S16, True, "frames")),
    0x1C: _ops(("speed", U8, False, "number")),
    0x1F: _ops(("unit", U16, False, "unit"), ("unit2", U16, False, "unit"), ("keep_yaw", U8, False, "flag")),
    0x21: _ops(("sound", U16, False, "sound")),
    0x22: _ops(("track", U8, False, "music"), ("volume", U8, False, "number"), ("fade", U8, False, "frames")),
    0x25: _ops(("unit", U16, False, "unit"), ("unit2", U16, False, "unit")),
    0x28: _ops(("unit", U16, False, "unit"), ("x", U8, False, "x"), ("y", U8, False, "y"),
               ("level", U8, False, "level"), ("speed", S16, True, "speed"), ("terrain", U8, False, "flag")),
    0x29: _ops(("unit", U16, False, "unit")),
    0x2C: _ops(("unit", U16, False, "unit"), ("unit2", U16, False, "units"), ("style", U8, False, "number"),
               ("speed", U8, False, "turn_speed"), ("delay", U8, False, "frames")),
    0x2D: _ops(("unit", U16, False, "units"), ("facing", U8, False, "facing16"), ("style", U8, False, "number"),
               ("speed", U8, False, "turn_speed"), ("delay", U8, False, "frames")),
    0x2E: _ops(("top_red", U8, False, "colour"), ("top_green", U8, False, "colour"),
               ("top_blue", U8, False, "colour"), ("bottom_red", U8, False, "colour"),
               ("bottom_green", U8, False, "colour"), ("bottom_blue", U8, False, "colour"),
               ("frames", U8, False, "frames"), ("store", U8, False, "flag")),
    0x32: _ops(("unit", U16, False, "units"), ("style", U8, False, "number"), ("red", U8, True, "colour"),
               ("green", U8, True, "colour"), ("blue", U8, True, "colour"), ("frames", U8, False, "frames")),
    # ColorField: the map's colours as ColorUnit's a unit's (the
    # decompilation's `battle_map_color_field`): a mode, red, green and blue
    # (signed), and how fast (`colour_frames`).
    0x33: _ops(("style", U8, False, "number"), ("red", U8, True, "colour"), ("green", U8, True, "colour"),
               ("blue", U8, True, "colour"), ("frames", U8, False, "frames")),
    0x38: _ops(("speed", S16, True, "frames")),
    0x3B: _ops(("unit", U16, False, "unit"), ("dx", S16, True, "offset"), ("dy", S16, True, "offset"),
               ("dz", S16, True, "offset"), ("curve", U8, False, "number"), ("weight", U8, False, "number"),
               ("frames", U16, False, "frames")),
    0x3C: _ops(("weather", U16, False, "number")),
    0x3D: _ops(("unit", U16, False, "unit")),
    0x3E: _ops(("style", U8, False, "number"), ("red", U8, False, "colour"), ("green", U8, False, "colour"),
               ("blue", U8, False, "colour"), ("end_red", U8, False, "colour"),
               ("end_green", U8, False, "colour"), ("end_blue", U8, False, "colour"),
               ("frames", U16, False, "frames")),
    0x41: _ops(("step", U8, False, "number"), ("period", U8, False, "frames"),
               ("step2", U8, False, "number"), ("period2", U8, False, "frames")),
    0x43: _ops(("function", U8, False, "number")),
    0x44: _ops(("unit", U16, False, "unit")),
    0x45: _ops(("unit", U16, False, "unit"), ("hidden", U8, False, "flag")),
    0x46: _ops(("unit", U16, False, "unit")),
    0x47: _ops(("sprite", U16, False, "sprite"), ("unit", U8, False, "unit"), ("x", U8, False, "x"),
               ("y", U8, False, "y"), ("level", U8, False, "level"), ("facing", U8, False, "facing"),
               ("hidden", U8, False, "flag")),
    0x4C: _ops(("map", U16, False, "map")),
    0x4D: _ops(("frames", U8, False, "frames")),
    0x4E: _ops(("unit", U16, False, "unit"), ("flag", U8, False, "flag")),
    0x4F: _ops(("time", U8, False, "number")),
    0x50: _ops(("row", U8, False, "number")),
    0x51: _ops(("box", U8, False, "window"), ("line", U16, False, "line"), ("portrait", U16, False, "portrait")),
    0x53: _ops(("unit", U16, False, "unit"), ("unit2", U16, False, "units"), ("style", U8, False, "number"),
               ("speed", U8, False, "turn_speed"), ("delay", U8, False, "frames")),
    # The event's own animations (EVTCHR, `unit_sprites`): LoadEVTCHR puts a
    # block of the file in a slot, SaveEVTCHR its picture up, the two after
    # clear a slot; EVTCHR palette colours a unit with one of a slot's
    # palettes (the decompilation's `script_instruction.h`).
    0x58: _ops(("slot", U8, False, "number"), ("block", U16, False, "number")),
    0x59: _ops(("slot", U8, False, "number")),
    0x5A: _ops(("slot", U8, False, "number")),
    0x5B: _ops(("slot", U8, False, "number")),
    0x5E: _ops(("slot", U8, False, "number")),
    0x5F: _ops(("unit", U16, False, "unit"), ("x", U8, False, "x"), ("y", U8, False, "y"),
               ("level", U8, False, "level"), ("facing", U8, False, "facing")),
    0x60: _ops(("shift", U8, False, "number"), ("frames", U8, False, "frames")),
    0x63: _ops(("curve", U8, False, "number")),
    0x64: _ops(("unit", U16, False, "unit")),
    0x68: _ops(("unit", U16, False, "unit"), ("flag", U8, False, "flag")),
    0x69: _ops(("unit", U16, False, "units"), ("x", U8, False, "x"), ("y", U8, False, "y"),
               ("unused", U8, False, "number"), ("style", U8, False, "number"),
               ("speed", U8, False, "turn_speed"), ("delay", U8, False, "frames")),
    0x6F: _ops(("unit", U16, False, "unit")),
    0x70: _ops(("unit", U16, False, "unit"), ("length", U8, False, "number"), ("direction", U8, False, "number")),
    0x73: _ops(("x", S16, True, "camera"), ("height", S16, True, "camera"), ("y", S16, True, "camera"),
               ("tilt", S16, True, "angle"), ("yaw", S16, True, "angle"), ("roll", S16, True, "angle"),
               ("zoom", S16, True, "zoom")),
    0x78: _ops(("display", U8, False, "number"), ("frames", U8, False, "frames")),
    0x79: _ops(("unit", U16, False, "unit"), ("animation", U16, False, "animation")),
    0x7E: _ops(("variable", U16, False, "variable"), ("value", S16, True, "number")),
    0x7F: _ops(("unit", U16, False, "unit"), ("slot", U8, False, "number"), ("palette", U8, False, "number")),
    0x80: _ops(("unit", U16, False, "units"), ("frames", U8, False, "frames")),
    0x83: _ops(("unit", U16, False, "units"), ("stat", U8, False, "number"), ("delta", S16, True, "number")),
    0x84: _ops(("tune", U8, False, "number")),
    0x86: _ops(("unit", U16, False, "unit"), ("item", U8, False, "number")),
    0x87: _ops(("unit", U16, False, "unit"), ("unit2", U16, False, "unit")),
    0x8C: _ops(("unit", U16, False, "unit"), ("facing", U8, False, "facing"),
               ("animation", U16, False, "animation"), ("unused", U8, False, "number")),
    0x91: _ops(("dx", U8, True, "offset"), ("dy", U8, True, "offset"), ("step", U8, True, "number")),
    0x92: _ops(("unit", U16, False, "unit"), ("status", U8, False, "number"), ("frames", U16, False, "frames")),
    0x94: _ops(("unit", U16, False, "unit")),
    0x97: _ops(("unit", U16, False, "unit")),
    0x98: _ops(("unit", U16, False, "unit")),
    0x99: _ops(("unit", U16, False, "unit")),
    0xBE: _ops(("variable", U16, False, "variable")),
    0xC2: _ops(("line", U32, False, "line")),
    # The remaster's caption (a place's name, or words such as "At that
    # moment..."): a key of the game's `Caption` table (`caption_words`).
    0xE7: _ops(("caption", U32, False, "caption")),
    0xD0: _ops(("target", U8, False, "target")),
    0xD1: _ops(("target", U8, False, "target")),
    0xD2: _ops(("target", U8, False, "target")),
    0xD3: _ops(("target", U8, False, "target")),
    0xD4: _ops(("target", U8, False, "target")),
    0xD5: _ops(("target", U8, False, "target")),
    0xE5: _ops(("task", U16, False, "task")),
    0xEB: _ops(("line", U32, False, "line"), ("next_line", U32, False, "line"), ("more", U16, False, "number")),
    0xF1: _ops(("frames", S16, True, "frames")),
}
for _variable_op in range(0xB0, 0xBE):
    # Odd ones take a second variable, even ones a number.
    LAYOUTS[_variable_op] = _ops(("variable", U16, False, "variable"),
                                 ("value", U16, False, "variable" if _variable_op & 1 else "number"))
#: Where the remaster's layout differs: the text id 32 bits, and one byte
#: more at the end of DisplayMessage (0 in 2,608 of the game's, 1 in 11).
ENHANCED_LAYOUTS = {
    0x10: _ops(("thread", U8, False, "number"), ("box", U8, False, "box"), ("line", U32, False, "line"),
               ("unit", U16, False, "unit"), ("portrait", U8, False, "portrait"),
               ("dx", S16, True, "offset"), ("dy", S16, True, "offset"), ("arrow", S16, True, "offset"),
               ("options", U8, False, "number"), ("last", U8, False, "number")),
    0x51: _ops(("box", U8, False, "window"), ("line", U32, False, "line"), ("portrait", U16, False, "portrait")),
}
#: ChangeDialog's text id that closes its box instead.
CLOSE_BOX = {"enhanced": 0xFFFFFFFF, "classic": 0xFFFF}


def layout(opcode: int, mode: str = "enhanced") -> tuple:
    """The operands of `opcode` in `mode`, or () when they aren't known."""
    if mode == "enhanced" and opcode in ENHANCED_LAYOUTS:
        return ENHANCED_LAYOUTS[opcode]
    return LAYOUTS.get(opcode, ())


def operand(instruction: Instruction, name: str, mode: str = "enhanced") -> Optional[int]:
    """The number operand `name` of `instruction` holds, or None when it has none of that name."""
    for spec in layout(instruction.opcode, mode):
        if spec.name == name:
            raw = bytes(instruction.operands[spec.at:spec.at + spec.size])
            if len(raw) < spec.size:
                return None
            return int.from_bytes(raw, "little", signed=spec.signed)
    return None


def operands(instruction: Instruction, mode: str = "enhanced") -> dict:
    """`{name: number}` for every known operand of `instruction`."""
    return {spec.name: operand(instruction, spec.name, mode) for spec in layout(instruction.opcode, mode)}


def operand_range(spec: Operand) -> tuple:
    bits = 8 * spec.size
    return (-(1 << (bits - 1)), (1 << (bits - 1)) - 1) if spec.signed else (0, (1 << bits) - 1)


def with_operands(instruction: Instruction, mode: str = "enhanced", **values) -> Instruction:
    """`instruction` with the named operands set, every other byte as it was. Raises ScriptError
    for a name the instruction hasn't or a number that doesn't fit."""
    data = bytearray(instruction.operands)
    specs = {spec.name: spec for spec in layout(instruction.opcode, mode)}
    for name, value in values.items():
        spec = specs.get(name)
        if spec is None:
            raise ScriptError(f"instruction {instruction.opcode:02X} has no operand named {name}")
        low, high = operand_range(spec)
        value = int(value)
        if not low <= value <= high:
            raise ScriptError(f"{value} doesn't fit {name} ({low} to {high})")
        data[spec.at:spec.at + spec.size] = value.to_bytes(spec.size, "little", signed=spec.signed)
    return Instruction(instruction.opcode, bytes(data))


def make(opcode: int, lengths: Lengths, mode: str = "enhanced", **values) -> Instruction:
    """A new instruction, every operand 0 but those given."""
    blank = Instruction(opcode, bytes(lengths.of(mode)[opcode]))
    return with_operands(blank, mode, **values) if values else blank


# =============================================================================
# Nodes: what the Event Editor shows as one card
# =============================================================================

#: The kinds of node, each the page's colour and the node list's heading.
KINDS = ("talk", "units", "camera", "screen", "sound", "wait", "story", "other")
_KIND_OF = {}
for _kind, _codes in {
    "talk": (0x10, 0x51, 0x25, 0x26, 0x37, 0x50, 0xEB, 0xC2),
    "units": (0x11, 0x28, 0x2C, 0x2D, 0x32, 0x3B, 0x3D, 0x44, 0x45, 0x46, 0x47, 0x4E, 0x53, 0x5F, 0x62,
              0x68, 0x69, 0x6E, 0x70, 0x79, 0x7A, 0x80, 0x81, 0x83, 0x86, 0x87, 0x8C, 0x92, 0x94, 0x97,
              0x98, 0x99, 0x6C, 0x6D, 0x7F, 0x58, 0x59, 0x5A, 0x5B, 0x5C, 0x5D),
    "camera": (0x19, 0x1D, 0x1E, 0x1F, 0x38, 0x63, 0x73, 0xC0, 0x41, 0x42),
    "screen": (0x1A, 0x1B, 0x2E, 0x31, 0x33, 0x3E, 0x4D, 0x4F, 0x3C, 0x76, 0x77, 0x7D, 0x91, 0x18, 0x8A,
               0x8B, 0x54, 0x55, 0x66, 0x88, 0x89, 0x3F, 0x40),
    "sound": (0x21, 0x22, 0x5E, 0x60, 0x6A, 0x6B, 0x7C, 0x84),
    "wait": (0xF1, 0xE5, 0x29, 0x12, 0x16, 0x39, 0x3A, 0x48, 0x4B, 0x56, 0x57, 0x64, 0x65, 0x6F, 0x7E,
             0x8E, 0xF0, 0xF2, 0x7B),
    "story": (0x13, 0x4C, 0x43, 0x78, 0x82, 0x85, 0x8F, 0x90, 0x93, 0x96, 0x27, 0x1C, 0x71, 0x72,
              0xA0, 0xA1, 0xA2, 0xA3, 0xA4, 0xA5, 0xBE, 0xD0, 0xD1, 0xD2, 0xD3, 0xD4, 0xD5, 0xD8, 0xD9,
              0xDA, 0xDB, 0xDC, 0xE0, 0xE3, 0x2A, 0x2B, 0x49, 0x4A) + tuple(range(0xB0, 0xBE)),
}.items():
    for _code in _codes:
        _KIND_OF[_code] = _kind


def kind_of(opcode: int) -> str:
    return _KIND_OF.get(opcode, "other")


#: WaitForInstruction's tasks (the decompilation's `thread_task_e`); 67 a
#: unit's status (InflictStatus's thread).
TASK_MESSAGE, TASK_CAMERA, TASK_BLOCK = 1, 4, 8
TASK_DARKNESS, TASK_LIGHT, TASK_SPRITE_MOVE, TASK_SCREEN = 6, 7, 11, 12
TASK_STATUS = 67


@dataclass
class Node:
    """A run of a script's instructions shown as one card: `first` and `count`
    in the script's instruction list, `shape` saying what grouped them."""
    first: int
    count: int
    kind: str
    shape: str

    def indexes(self) -> range:
        return range(self.first, self.first + self.count)


def _is_wait_task(instruction: Instruction, task: int) -> bool:
    return instruction.opcode == 0xE5 and instruction.operands[:2] == task.to_bytes(2, "little")


def _unit16(instruction: Instruction) -> int:
    return int.from_bytes(instruction.operands[:2], "little")


def _matching_end(instructions: list, at: int, start: int, end: int) -> Optional[int]:
    depth = 0
    for i in range(at, len(instructions)):
        opcode = instructions[i].opcode
        if opcode == start:
            depth += 1
        elif opcode == end:
            depth -= 1
            if depth == 0:
                return i
    return None


def group_nodes(script: Script) -> list:
    """
    The script as nodes, in order, covering every instruction once.

    Grouped: a DisplayMessage or ChangeDialog with the waits for its button
    after it ("speak", "words"); units added one after another, each with its
    wait ("add_units"); a block of instructions that run together, from
    BlockStart to BlockEnd ("together"), or a camera path from
    CameraFusionStart to its end ("camera_path"), or the units added
    together (AddUnitStart to its end and wait, "add_together"); a camera
    with the curve, focus and speed set just before it and the wait for it
    after ("camera"); a walk with the animation it walks in ("walk"); turns
    of one unit in a row, each with its waits ("turns"); a unit teleported in
    and drawn ("appear"). Everything else is a node of its own ("single").
    """
    out, i, items = [], 0, script.instructions
    n = len(items)
    while i < n:
        op = items[i].opcode
        start, shape = i, "single"
        if op == 0x10:
            i += 1
            while i < n and _is_wait_task(items[i], TASK_MESSAGE):
                i += 1
            shape = "speak"
        elif op == 0x51:
            i += 1
            while i < n and _is_wait_task(items[i], TASK_MESSAGE):
                i += 1
            shape = "words"
        elif op == 0x45:
            while i < n and items[i].opcode == 0x45:
                i += 1
                if i < n and items[i].opcode == 0x48:
                    i += 1
            shape = "add_units"
        elif op in (0x2A, 0x1D, 0x49):
            closing = {0x2A: 0x2B, 0x1D: 0x1E, 0x49: 0x4A}[op]
            end = _matching_end(items, i, op, closing)
            if end is None:
                i += 1
            else:
                i = end + 1
                if op == 0x49 and i < n and items[i].opcode == 0x4B:
                    i += 1
                if op == 0x1D:
                    while i < n and _is_wait_task(items[i], TASK_CAMERA):
                        i += 1
                shape = {0x2A: "together", 0x1D: "camera_path", 0x49: "add_together"}[op]
        elif op in (0x63, 0x1F, 0x38, 0x19, 0x73):
            j = i
            while j < n and items[j].opcode in (0x63, 0x1F, 0x38, 0x73):
                j += 1
            if j < n and items[j].opcode == 0x19:
                i = j + 1
                while i < n and _is_wait_task(items[i], TASK_CAMERA):
                    i += 1
                shape = "camera"
            else:
                i += 1
        elif op == 0x28:
            i += 1
            if i < n and items[i].opcode == 0x79 and _unit16(items[i]) == _unit16(items[start]):
                i += 1
            shape = "walk"
        elif op == 0x2D:
            unit = _unit16(items[i])
            turns = 0
            while i < n and items[i].opcode == 0x2D and _unit16(items[i]) == unit:
                i += 1
                turns += 1
                while i < n and ((items[i].opcode == 0x64 and _unit16(items[i]) == unit)
                                 or items[i].opcode == 0x65
                                 or (items[i].opcode == 0xF1 and i + 1 < n
                                     and items[i + 1].opcode in (0x2D, 0x64, 0x65)
                                     and (items[i + 1].opcode != 0x2D or _unit16(items[i + 1]) == unit))):
                    i += 1
            shape = "turns" if turns > 1 else "turn"
        elif op == 0x98:
            i += 1
            if i < n and items[i].opcode == 0x44 and _unit16(items[i]) == _unit16(items[start]):
                i += 1
            shape = "appear"
        else:
            i += 1
        out.append(Node(start, i - start, kind_of(items[start].opcode), shape))
    return out


def node_instructions(script: Script, node: Node) -> list:
    return script.instructions[node.first:node.first + node.count]


def replace_node(script: Script, nodes: list, index: int, instructions) -> Script:
    """The script with node `index`'s instructions replaced (an empty list takes it away)."""
    node = nodes[index]
    items = list(script.instructions)
    items[node.first:node.first + node.count] = list(instructions)
    return script.with_instructions(items)


def insert_instructions(script: Script, nodes: list, before: int, instructions) -> Script:
    """The script with `instructions` put before node `before` (its length: at the end, before END)."""
    items = list(script.instructions)
    if before < len(nodes):
        at = nodes[before].first
    else:
        at = len(items)
        while at > 0 and items[at - 1].opcode == END:
            at -= 1
    items[at:at] = list(instructions)
    return script.with_instructions(items)


def move_node(script: Script, nodes: list, index: int, before: int) -> Script:
    """The script with node `index` moved to stand before node `before`."""
    node = nodes[index]
    items = list(script.instructions)
    moved = items[node.first:node.first + node.count]
    del items[node.first:node.first + node.count]
    if before >= len(nodes):
        at = len(items)
        while at > 0 and items[at - 1].opcode == END:
            at -= 1
    else:
        at = nodes[before].first
        if at > node.first:
            at -= node.count
    items[at:at] = moved
    return script.with_instructions(items)


# =============================================================================
# The scene: its units and its words
# =============================================================================

FIFTH_ENTD = "fftpack/event_btlevt_bin_entrydata_add_ent.bin"
#: The fifth file's battles start here (the PSP's War of the Lions battles).
FIFTH_FIRST = 0x200
#: Unit ids that aren't a unit of the battle: every unit, the player's five
#: deployed units, a team (the decompilation's unit selectors).
EVERY_UNIT = 0
PARTY_UNITS = range(0x78, 0x7D)
#: Animations from these are a sequence of EVTCHR slot 0's block, and slot 1's (`unit_sprites`).
EVTCHR_ANIMATIONS = (500, 600)
TEAM_GROUPS = range(0x100, 0x110)


def battle_units(game_dir, battle: int) -> list:
    """The units of ENTD battle `battle` (`entd.EventUnit`, the occupied
    slots), from the four `battle_entd` files or, from 512, the fifth."""
    if not game_dir or battle is None or battle < 0:
        return []
    game = Path(game_dir)
    if battle < FIFTH_FIRST:
        name = entd.ENTD_FILENAMES[battle // entd.EVENTS_PER_FILE] if battle // entd.EVENTS_PER_FILE < len(
            entd.ENTD_FILENAMES) else None
        if name is None:
            return []
        path, base = game / entd.ENTD_FOLDER / name, (battle % entd.EVENTS_PER_FILE) * entd.EVENT_BYTES
    else:
        path, base = game / FIFTH_ENTD, (battle - FIFTH_FIRST) * entd.EVENT_BYTES
    try:
        with open(path, "rb") as handle:
            handle.seek(base)
            block = handle.read(entd.EVENT_BYTES)
    except OSError:
        return []
    if len(block) < entd.EVENT_BYTES:
        return []
    units = [entd.read_unit(block[s * entd.UNIT_BYTES:(s + 1) * entd.UNIT_BYTES], battle, s)
             for s in range(entd.UNITS_PER_EVENT)]
    return [u for u in units if u.occupied]


def fifth_battle_count(game_dir) -> int:
    try:
        return (Path(game_dir) / FIFTH_ENTD).stat().st_size // entd.EVENT_BYTES
    except (OSError, TypeError):
        return 0


def scene_text_files(sqlite_path, number: int) -> list:
    """
    The text files event `number`'s words are in, without the language
    (`nxd/text/scenario/scenario0010`), from `ScenarioId` (its `EventIds`)
    and `ScionFiles` in the converted database. Empty when it says nothing.
    """
    if not sqlite_path:
        return []
    try:
        db = sqlite3.connect(f"file:{Path(sqlite_path).as_posix()}?mode=ro", uri=True)
    except sqlite3.Error:
        return []
    try:
        files = {key: path for key, path in db.execute("SELECT Key, File FROM ScionFiles")}
        out = []
        for _key, events, text in db.execute("SELECT Key, EventIds, UnknownC FROM ScenarioId"):
            try:
                ids = json.loads(events) if isinstance(events, str) else events
            except (TypeError, ValueError):
                continue
            if isinstance(ids, int):
                ids = [ids]
            if number in (ids or []) and text in files:
                stem = re.sub(r"\.pzd$", "", str(files[text]), flags=re.IGNORECASE)
                if stem not in out:
                    out.append(stem)
        return out
    except sqlite3.Error:
        return []
    finally:
        db.close()


def speaker_names(sqlite_path, language: str = "en") -> dict:
    """`{Speaker key: name}` in `language` (the name over a speech box)."""
    if not sqlite_path:
        return {}
    try:
        db = sqlite3.connect(f"file:{Path(sqlite_path).as_posix()}?mode=ro", uri=True)
    except sqlite3.Error:
        return {}
    try:
        return {key: name for key, name in db.execute(f'SELECT Key, Name FROM "Speaker-{language}"') if name}
    except sqlite3.Error:
        return {}
    finally:
        db.close()


def next_line_id(lines) -> int:
    """A line id no line of `lines` has: one past the highest, so a file kept in id order stays so."""
    return max((line.line_id for line in lines), default=0) + 1


# =============================================================================
# Playing a script out: what is on screen at each frame
# =============================================================================

@dataclass
class Camera:
    """The game's camera: where it looks (x, height, y: four times the world's
    units, as the CAMERA instruction keeps them), its angles (4,096 a turn)
    and zoom (4,096 usual)."""
    x: float = 0.0
    height: float = 0.0
    y: float = 0.0
    tilt: float = 0.0
    yaw: float = 0.0
    roll: float = 0.0
    zoom: float = 4096.0

    def values(self) -> tuple:
        return (self.x, self.height, self.y, self.tilt, self.yaw, self.roll, self.zoom)


#: A CAMERA component of this value keeps the camera's own.
KEEP = 10000
#: Animations the game puts a unit in itself (the decompilation's
#: `animation.h`): standing (a scene's units as they are made, InflictStatus
#: on a unit that lives), and kneeling (InflictStatus's poison).
STAND, KNEEL = 2, 22


@dataclass
class Pose:
    """A unit at one moment."""
    unit_id: int
    x: float
    y: float
    level: int
    facing: float          # sixteenths of a turn: 0 south, 4 west, 8 north, 12 east
    shown: bool
    alpha: float = 1.0
    #: None: the waiting walk in place, a march (the game's animation for a
    #: unit in battle with no status: `animation_set_for_status`).
    animation: Optional[int] = None
    since: int = 0                     # the frame the animation started
    walking: bool = False
    lift: tuple = (0.0, 0.0, 0.0)      # a sprite move's offset, world units
    #: Its colours changed by ColorUnit: `(matrix, offset)` (`colour_change`); None: its own.
    tint: Optional[tuple] = None
    #: The block of the event animations' file (EVTCHR) an animation from 500
    #: plays from: the one its slot held when it was set (None: none loaded).
    evtchr: Optional[int] = None
    #: A palette of a block the unit is coloured with (EVTCHR palette): (block, palette).
    colours: Optional[tuple] = None


@dataclass
class BoxShown:
    """A speech box open at one moment."""
    window: int
    line: int
    unit: int
    box: int
    portrait: int
    dx: int
    dy: int
    arrow: int
    options: int
    opened: int                        # the frame it opened
    instruction: int                   # the DisplayMessage that opened it


@dataclass
class CaptionShown:
    """A caption on screen (the remaster's `E7`): its `Caption` key, how many
    frames since it began and how many until it has gone."""
    key: int
    since: float
    left: float


@dataclass
class Frame:
    """Everything on screen at one frame."""
    frame: int
    units: list
    camera: Optional[Camera]
    boxes: list
    screen: tuple                      # (red, green, blue, alpha 0 to 1) over the map
    map_number: Optional[int] = None
    #: The map's colours changed by ColorField: `(matrix, offset)` (`colour_change`); None: its own.
    field: Optional[tuple] = None
    caption: Optional[CaptionShown] = None


@dataclass
class SceneUnit:
    """A unit the scene starts with or adds: its ENTD slot (None for a ghost
    or the player's party) and where it stands."""
    unit_id: int
    sprite_set: int
    job: int
    palette: int
    x: int
    y: int
    level: int
    facing: int            # quarter turns
    shown: bool
    slot: Optional[int] = None
    team: int = 0
    ghost_sprite: Optional[int] = None
    #: One of the player's party, not the battle's: drawn as the sprite set of its own number.
    party: bool = False
    #: One of them the script places nowhere: where the player's units stand (`scene_units`).
    deployed: bool = False
    #: The ENTD slot's `unit_name` (a `CharaName` key), for its name.
    name_id: int = 0


#: An ENTD slot whose unit id is this holds no unit the script can name.
NO_UNIT_ID = 0xFF
#: Story characters' unit ids: the player's party, when the battle hasn't them.
STORY_UNITS = range(1, 0x78)
#: Unit ids the game fills in as the event runs (the decompilation's
#: `EVENT_UNIT_SELECTOR_*`): a scenario's four (0x64 to 0x67), the first
#: important ENTD unit (0x68) and the unit taking its turn (0x69).
SELECTOR_UNITS = range(0x64, 0x6A)
#: Ramza's story ids, a chapter's each: placed first, on the first tile.
RAMZA_UNITS = (1, 2, 3)
#: A DisplayMessage's box kinds (its 0x70 bits) that are a speaker's box with
#: their face: 0x10, and 0x70, which the dialog thread makes a 0x10 at the top
#: or bottom of the screen as the speaker faces the camera (the
#: decompilation's `message_dialog_thread`; 720 of the game's 2,361 enhanced
#: boxes, most of them in battles).
SPEECH_KINDS = (0x10, 0x70)
#: The kind placed by its speaker's facing.
FACING_KIND = 0x70
#: A box with this bit has no tail: it doesn't point at its speaker.
NO_TAIL = 0x08


def is_speech(box: int) -> bool:
    """Whether a DisplayMessage's box type is a speaker's box (`SPEECH_KINDS`)."""
    return box & 0x70 in SPEECH_KINDS


def points_at_speaker(box: int) -> bool:
    """Whether a DisplayMessage's box points its tail at its speaker."""
    return is_speech(box) and not box & NO_TAIL


def facing_window(box: int, facing: float, camera_yaw: float) -> int:
    """
    Where a box of the facing kind (0x70) goes: 1 at the top of the screen,
    2 at the bottom, as the dialog thread's `unit_check_facing_relative_to_camera`
    works it out from the speaker's facing (sixteenths) and the camera's yaw
    (4,096ths) as it opens; another box's own window (its low two bits).
    """
    if box & 0x70 != FACING_KIND:
        return box & 3
    yaw = int(camera_yaw) % 4096
    turned = ((((yaw + 0x200) & 0xF00) >> 8) + int(round(facing))) & 0xF
    return 2 if 0 <= turned - 7 < 6 else 1

#: ATTACK.OUT's deployment squads (the decompilation's `deploy_squad_t`, where
#: `g_deploy_squad_data` points: 0x801CABD4, the file loaded at 0x801BF000):
#: 12 bytes each, numbered as a scenario's row names them (two u16 at 9).
SQUADS_AT, SQUAD_BYTES, SQUAD_MOST = 0xBBD4, 12, 0x300
SCENARIO_SQUADS_AT = 9


def is_story_unit(unit_id: int) -> bool:
    """A story character's unit id (Ramza 1 to 3, Delita, Agrias...), not one the game picks as it runs."""
    return unit_id in STORY_UNITS and unit_id not in SELECTOR_UNITS


@dataclass(frozen=True)
class Squad:
    """One of ATTACK.OUT's deployment squads (see the module's notes)."""
    tiles: int              # 5 by 5, a bit a tile, the first five the first row
    x: int                  # the middle tile, on the map
    y: int
    level: int
    orientation: int        # how the grid is turned (its byte, both halves)
    most: int               # how many units it takes
    map: int


def read_squad(attack_out: bytes, number: int) -> Optional[Squad]:
    """Squad `number` of ATTACK.OUT, or None past the table or the file."""
    at = SQUADS_AT + SQUAD_BYTES * number
    if not 0 <= number < SQUAD_MOST or at + SQUAD_BYTES > len(attack_out):
        return None
    tiles, x, y, level, orientation, most, map_number = struct.unpack_from("<IbbBBBB", attack_out, at)
    return Squad(tiles, x, y, level, orientation, most, map_number)


def squad_tiles(squad: Squad) -> list:
    """
    `[(x, y, level, facing)]`: the map tiles a squad's units may stand on,
    in the order the game fills them. The grid's bits are laid on the
    screen's 5 by 5 as the orientation's low half says
    (`deploy_prepare_valid_tiles`), then each tile, row by row, is put on
    the map about the middle tile and the units faced as the two halves
    together say (`attack_deployment_entrypoint`).
    """
    low = squad.orientation & 0x0F
    if low > 3:
        return []
    order = {0: [(y, x) for y in range(5) for x in range(5)],
             1: [(y, x) for x in range(4, -1, -1) for y in range(5)],
             2: [(y, x) for y in range(4, -1, -1) for x in range(4, -1, -1)],
             3: [(y, x) for x in range(5) for y in range(4, -1, -1)]}[low]
    usable = {cell for bit, cell in enumerate(order) if squad.tiles >> bit & 1}
    turn = (low - 1 + (squad.orientation >> 4)) % 4
    facing = (0, 3, 2, 1)[turn]
    out = []
    for row in range(5):
        for column in range(5):
            if (row, column) not in usable:
                continue
            if turn == 0:
                x, y = squad.x - column + 2, squad.y + row - 2
            elif turn == 1:
                x, y = squad.x - row + 2, squad.y - column + 2
            elif turn == 2:
                x, y = squad.x + column - 2, squad.y - row + 2
            else:
                x, y = squad.x + row - 2, squad.y + column - 2
            out.append((x, y, squad.level & 1, facing))
    return out


@dataclass(frozen=True)
class Deployment:
    """Where the player's units stand as a battle starts: its map, and its squads' tiles in the order filled."""
    map: int
    tiles: tuple


def deployment(attack_out: bytes, number: int) -> Optional[Deployment]:
    """Scenario `number`'s deployment, from ATTACK.OUT's bytes; None when it deploys no one."""
    at = bm.SCENARIOS_AT
    while at + bm.SCENARIO_BYTES <= len(attack_out):
        row = attack_out[at:at + bm.SCENARIO_BYTES]
        if not any(row):
            return None
        if struct.unpack_from("<H", row, 0)[0] == number:
            break
        at += bm.SCENARIO_BYTES
    else:
        return None
    tiles, map_number = [], None
    for squad_number in struct.unpack_from("<HH", row, SCENARIO_SQUADS_AT):
        squad = read_squad(attack_out, squad_number) if squad_number else None
        # A squad without tiles the game swaps for its first, a test of its own.
        if squad is None or not squad.tiles:
            continue
        map_number = squad.map if map_number is None else map_number
        tiles += [t for t in squad_tiles(squad) if t not in tiles]
    return Deployment(map_number, tuple(tiles)) if tiles else None


def _scenario_row(attack_out: bytes, number: int) -> Optional[bytes]:
    """Scenario `number`'s 24 bytes in ATTACK.OUT's table, or None."""
    at = bm.SCENARIOS_AT
    while at + bm.SCENARIO_BYTES <= len(attack_out):
        row = attack_out[at:at + bm.SCENARIO_BYTES]
        if not any(row):
            return None
        if struct.unpack_from("<H", row, 0)[0] == number:
            return row
        at += bm.SCENARIO_BYTES
    return None


#: Where a scenario's two tracks are in its row (`scenario_setup_t`'s
#: `music_1` and `music_2`): PlayStation music ids, 0 for none.
SCENARIO_MUSIC_AT = 5


def scenario_music(attack_out: bytes, number: int) -> tuple:
    """
    Scenario `number`'s two tracks, `(first, second)` PlayStation music ids
    (0: none), from ATTACK.OUT's table: the first plays as the event starts
    and SwitchTrack takes turns between them (`music_play_tracks`). The
    remaster keeps the same numbers in its program's setup records, which a
    mod can't change through the mod loader's tables.
    """
    row = _scenario_row(attack_out, number)
    if row is None:
        return (0, 0)
    return (row[SCENARIO_MUSIC_AT], row[SCENARIO_MUSIC_AT + 1])


def scenario_music_from_game(game_dir, number: int) -> tuple:
    """`scenario_music` from the unpacked game's ATTACK.OUT, `(0, 0)` without it."""
    if not game_dir:
        return (0, 0)
    try:
        return scenario_music((Path(game_dir) / bm.SCENARIO_FILE).read_bytes(), number)
    except OSError:
        return (0, 0)


def music_titles(sqlite_path, language: str = "en") -> dict:
    """
    `{PlayStation music id: title}`: the names the game gives its music
    (`BGMMode-<lang>`, as its sound test lists them, each a `SoundEnhanced`
    row whose `Unknown10` is the PlayStation's id); `{}` without the database.
    """
    if not sqlite_path:
        return {}
    try:
        con = sqlite3.connect(f"file:{Path(sqlite_path).as_posix()}?mode=ro", uri=True)
    except sqlite3.Error:
        return {}
    out = {}
    try:
        ids = {key: psx for key, psx in con.execute("SELECT Key, Unknown10 FROM SoundEnhanced")}
        for title, enhanced in con.execute(f'SELECT Title, SoundEnhancedId FROM "BGMMode-{language}"'):
            psx = ids.get(enhanced)
            if psx and title and psx not in out:
                out[int(psx)] = str(title)
    except sqlite3.Error:
        return {}
    finally:
        con.close()
    return out


#: A `Caption` row's `UnionId` names the table its words are in.
_CAPTION_TABLES = {"PlaceName": ("PlaceName", "Title"), "CaptionFreeWord": ("CaptionFreeWord", "Word")}


def caption_words(sqlite_path, language: str = "en") -> dict:
    """
    `{Caption key: words}` for the remaster's captions (`E7`): a `Caption`
    row's `UnionId` names a place (`PlaceName:N`) or words of their own
    (`CaptionFreeWord:N`, a new line between two lines); `{}` without the
    database.
    """
    if not sqlite_path:
        return {}
    try:
        con = sqlite3.connect(f"file:{Path(sqlite_path).as_posix()}?mode=ro", uri=True)
    except sqlite3.Error:
        return {}
    out = {}
    try:
        for key, union in con.execute("SELECT Key, UnionId FROM Caption"):
            table, _, number = str(union or "").partition(":")
            if table not in _CAPTION_TABLES or not number.isdigit():
                continue
            name, column = _CAPTION_TABLES[table]
            row = con.execute(f'SELECT "{column}" FROM "{name}-{language}" WHERE Key = ?', (int(number),)).fetchone()
            if row and row[0]:
                out[int(key)] = str(row[0])
    except sqlite3.Error:
        return {}
    finally:
        con.close()
    return out


def deployment_from_game(game_dir, number: int) -> Optional[Deployment]:
    """Scenario `number`'s deployment from the unpacked game's ATTACK.OUT, or None."""
    if not game_dir:
        return None
    try:
        return deployment((Path(game_dir) / bm.SCENARIO_FILE).read_bytes(), number)
    except OSError:
        return None


def scene_units(entd_units, instructions, deployed: Optional[Deployment] = None, tiles=None,
                mode: str = "enhanced") -> dict:
    """
    `{unit id: SceneUnit}`: the ENTD battle's units, those the script adds
    (AddUnit) not shown at first, the others at their ENTD place, facing as
    the ENTD faces them. A unit id two slots share is the first's; a slot
    of unit id 255 is none the script can name.

    A story character the script places (WarpUnit) but the battle hasn't is
    one of the player's party: Ramza is unit 3 in WotL's event 538 on
    Limberry Castle, and sprite set 3 is "Ramza, chapter 4". It stands
    where it is first placed, drawn as the sprite set of its own number.

    One it names but places nowhere is one the player deployed: on
    `deployed`'s tiles, Ramza first, then in the order the script names
    them; with no tile left for it, beside the first unit it speaks to (on
    `tiles`, `{(x, y)}`, when given). Every one of them is `party` and
    `deployed`.
    """
    added = {_unit16(i) for i in instructions if i.opcode == 0x45}
    out = {}
    for unit in entd_units:
        v = unit.values
        unit_id = int(v.get("unit_id", 0))
        if unit_id in out or unit_id in PARTY_UNITS or unit_id == NO_UNIT_ID:
            continue
        out[unit_id] = SceneUnit(unit_id, int(v.get("sprite_set", 0)), int(v.get("main_job", 0)),
                                 int(v.get("palette", 0)), int(v.get("x", 0)), int(v.get("y", 0)),
                                 int(bool(v.get("upper_level"))), int(v.get("facing", 0)) & 3,
                                 unit_id not in added, unit.slot, int(v.get("team", 0)),
                                 name_id=int(v.get("unit_name", 0)))
    for item in instructions:
        if item.opcode != 0x5F or len(item.operands) < 6:
            continue
        unit_id = _unit16(item)
        if unit_id in out or not is_story_unit(unit_id):
            continue
        x, y, level, facing = item.operands[2], item.operands[3], item.operands[4], item.operands[5]
        out[unit_id] = SceneUnit(unit_id, unit_id, 0, 0, x, y, level & 1, facing & 3, True, party=True)
    _deploy(out, instructions, deployed, tiles, mode)
    return out


def _speech_unit(item: Instruction, mode: str) -> Optional[int]:
    """The speaker of a DisplayMessage whose box points at its speaker, or None."""
    if item.opcode != 0x10:
        return None
    box, unit = operand(item, "box", mode), operand(item, "unit", mode)
    if box is None or unit is None or not points_at_speaker(box):
        return None
    return unit


def named_units(instructions, mode: str = "enhanced") -> list:
    """The story characters a script names (moves, turns, speaks as...), in the order it first names them."""
    out = []
    for item in instructions:
        if item.opcode == 0x10:
            found = [_speech_unit(item, mode)]
        else:
            found = [operand(item, spec.name, mode) for spec in layout(item.opcode, mode)
                     if spec.kind in ("unit", "units")]
        for unit_id in found:
            if unit_id is not None and is_story_unit(unit_id) and unit_id not in out:
                out.append(unit_id)
    return out


def _deploy(out: dict, instructions, deployed: Optional[Deployment], tiles, mode: str) -> None:
    """The story characters the script names that `out` hasn't, put where the player's units stand."""
    missing = [u for u in named_units(instructions, mode) if u not in out]
    missing.sort(key=lambda u: u not in RAMZA_UNITS)
    taken = {(u.x, u.y) for u in out.values()}
    free = [t for t in (deployed.tiles if deployed is not None else ()) if (t[0], t[1]) not in taken]
    speakers = [(index, _speech_unit(item, mode)) for index, item in enumerate(instructions)]
    speakers = [(index, unit) for index, unit in speakers if unit is not None]
    for unit_id in missing:
        if free:
            x, y, level, facing = free.pop(0)
        else:
            beside = _beside(out, unit_id, speakers, taken, tiles)
            if beside is None:
                continue
            x, y, level, facing = beside
        taken.add((x, y))
        out[unit_id] = SceneUnit(unit_id, unit_id, 0, 0, x, y, level, facing, True, party=True, deployed=True)


#: Beside a unit: the four tiles next to it, then the four corners.
_AROUND = ((0, 1), (1, 0), (0, -1), (-1, 0), (1, 1), (-1, 1), (1, -1), (-1, -1))


def _beside(out: dict, unit_id: int, speakers: list, taken: set, tiles) -> Optional[tuple]:
    """`(x, y, level, facing)` beside the first unit `unit_id` speaks to (the speaker before
    its first words, else after), facing it; None with no one in the scene to stand by."""
    own = [k for k, (_index, unit) in enumerate(speakers) if unit == unit_id]
    order = []
    if own:
        first = own[0]
        order = [unit for _i, unit in reversed(speakers[:first])] + [unit for _i, unit in speakers[first + 1:]]
    else:
        order = [unit for _i, unit in speakers]
    partner = next((out[u] for u in order if u != unit_id and u in out), None)
    if partner is None:
        partner = next((u for u in out.values() if u.shown), None)
    if partner is None:
        return None
    for dx, dy in _AROUND:
        x, y = partner.x + dx, partner.y + dy
        if x < 0 or y < 0 or (x, y) in taken or (tiles is not None and (x, y) not in tiles):
            continue
        # Faced towards it: west (1) is x falling, south (0) y falling.
        if abs(dx) >= abs(dy):
            facing = 1 if dx > 0 else 3
        else:
            facing = 0 if dy > 0 else 2
        return x, y, partner.level, facing
    return None


@dataclass
class _Track:
    """One unit's changes over the event, in the order they were made."""
    start: Pose
    changes: list = field(default_factory=list)   # (frame, kind, data)


# =============================================================================
# Colours: the map's (ColorField, 0x33) and the units' (ColorUnit, 0x32)
# =============================================================================

#: The colour modes (the decompilation's `battle_map_color_mode_e` and
#: `battle_map_palette_modify`): from the colours on screen (0 to 3) or the
#: colours kept (4 to 7), as they are, at half, grey ((2 red + 3 green +
#: blue) / 6) or grey at half, plus the red, green and blue given; 8 back to
#: the colours kept; 9 as 4, and back and again over and over in the game
#: (taken as 4: once); 10 changes nothing. The colours kept are the map's or
#: the unit's own, or what StoreModifiedMapPalette (0x66) kept of the map's.
COLOUR_RESTORE, COLOUR_STOP_REPEAT, COLOUR_REPEAT = 8, 10, 9
#: The PlayStation's colours have 31 steps a channel (five bits): an
#: instruction's red, green and blue are such steps, each 1/31 here.
COLOUR_STEPS = 31.0
_IDENTITY = (1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0)
_GREY = (2.0 / 6, 3.0 / 6, 1.0 / 6)


def _multiply(a: tuple, b: tuple) -> tuple:
    """Two 3 by 3 matrices (rows), a after b."""
    return tuple(sum(a[r * 3 + k] * b[k * 3 + c] for k in range(3)) for r in range(3) for c in range(3))


def colour_change(mode: int, red: int, green: int, blue: int, now: Optional[tuple] = None,
                  kept: Optional[tuple] = None) -> Optional[tuple]:
    """
    A colour mode's change, as `(matrix, offset)`: each colour (red, green
    and blue, 0 to 1) becomes matrix x colour + offset, clamped, drawn. Modes
    0 to 3 start from `now` (the change on screen), 4 to 7 and 9 from `kept`
    (None for either: the colours' own). 8 gives back `kept`, 10 `now`. The
    game leaves black alone (a colour of 0 is see through on the
    PlayStation); the drawing does too.
    """
    if mode == COLOUR_RESTORE:
        return kept
    if mode == COLOUR_STOP_REPEAT:
        return now
    source = now if mode < 4 else kept
    kind = (mode & 3) if mode < 8 else 0
    if kind == 0:
        matrix = _IDENTITY
    elif kind == 1:
        matrix = tuple(v / 2 for v in _IDENTITY)
    else:
        scale = 1.0 if kind == 2 else 0.5
        matrix = tuple(_GREY[c] * scale for _r in range(3) for c in range(3))
    offset = (red / COLOUR_STEPS, green / COLOUR_STEPS, blue / COLOUR_STEPS)
    if source is None:
        return (matrix, offset)
    m, o = source
    shifted = tuple(sum(matrix[r * 3 + k] * o[k] for k in range(3)) + offset[r] for r in range(3))
    return (_multiply(matrix, m), shifted)


def colour_frames(amount: int) -> int:
    """How long a colour change takes, from its last operand (the game's
    palette animations, `battle_map_update_color_animations`): at once for
    0, eight steps of a frame under 4, else 32 steps of `amount / 4` frames."""
    if amount <= 0:
        return 0
    if amount < 4:
        return 8
    return 32 * (amount >> 2)


def blend_change(a: Optional[tuple], b: Optional[tuple], t: float) -> Optional[tuple]:
    """`t` of the way from change `a` to change `b` (None: the colours' own)."""
    if t <= 0.0:
        return a
    if t >= 1.0:
        return b
    ma, oa = a if a is not None else (_IDENTITY, (0.0, 0.0, 0.0))
    mb, ob = b if b is not None else (_IDENTITY, (0.0, 0.0, 0.0))
    return (tuple(x + (y - x) * t for x, y in zip(ma, mb)), tuple(x + (y - x) * t for x, y in zip(oa, ob)))


def apply_change(change: Optional[tuple], colour: tuple) -> tuple:
    """`colour` (red, green, blue, 0 to 1) as `change` draws it, clamped; black left alone."""
    if change is None or not any(colour[:3]):
        return tuple(colour[:3])
    m, o = change
    return tuple(min(1.0, max(0.0, sum(m[r * 3 + k] * colour[k] for k in range(3)) + o[r])) for r in range(3))


def _changes_at(changes: list, frame: float, before: Optional[tuple] = None) -> Optional[tuple]:
    """The colour change on screen at `frame`, from `[(start, end, from, to)]` in order."""
    now = before
    for start, end, was, to in changes:
        if frame < start:
            break
        t = 1.0 if end <= start else min(1.0, (frame - start) / (end - start))
        now = blend_change(was, to, t)
    return now


# =============================================================================
# Captions (the remaster's E7) and music
# =============================================================================

#: A caption slides in and shows over `CAPTION_IN` frames
#: (`ffto_event_caption.uib`'s Show), stays, and goes over `CAPTION_OUT`
#: (its Hide), `CAPTION_FRAMES` after it began, unless another takes its place
#: sooner. How long it stays isn't in the layout: event 054's two captions
#: begin 330 frames apart, and this lets the first go before the second.
CAPTION_IN, CAPTION_OUT, CAPTION_FRAMES = 200, 60, 300
#: The game's music: a PlayStation music id (1 to 99) is the remaster's
#: `sound/music/music_<id less one, five digits>.sab` (`SoundEnhanced`'s
#: rows 150 up: row 150 + n is `music_000nn.sab`, its `Unknown10` n + 1).
MUSIC_FILE = "sound/music/music_{:05d}.sab"
#: A tune (PlayTune, 0x84) t is music 44 + t, played once while the
#: event's music fades out and back (the decompilation's `music.h`); Altima's
#: (CallFunction 0x0C) is music 19.
TUNE_BASE, ALTIMA_MUSIC = 44, 19
#: CallFunction's function that plays Altima's music.
CALL_ALTIMA_MUSIC = 0x0C
#: A SwitchTrack's volume: 0 to 96 in the script, 96 and up the loudest
#: (`script_scale_music_volume`).
MUSIC_VOLUME_MOST = 96


def music_file(music_id: int) -> Optional[str]:
    """The remaster's file for PlayStation music `music_id`, or None for none."""
    return MUSIC_FILE.format(music_id - 1) if 1 <= music_id <= 100 else None


@dataclass
class MusicPlayed:
    """
    A piece of music the event plays: PlayStation music `track`
    (`music_file`), from frame `start` to `end` (None: on past the event's
    end), at `volume` (0 to 1), coming in over `fade_in` frames, and going
    out over `fade_out` (`(start, end)` frames) when it fades. `slot` is the
    event's track it is (1 or 2), 0 for a tune, played once over the rest.
    """
    track: int
    start: float
    end: Optional[float] = None
    volume: float = 1.0
    fade_in: float = 0.0
    fade_out: Optional[tuple] = None
    slot: int = 1

    def volume_at(self, frame: float) -> float:
        """How loud it is at `frame` (0 to 1), its fades counted; 0 outside its time."""
        if frame < self.start or (self.end is not None and frame >= self.end):
            return 0.0
        level = self.volume
        if self.fade_in > 0 and frame < self.start + self.fade_in:
            level *= (frame - self.start) / self.fade_in
        if self.fade_out is not None and frame >= self.fade_out[0]:
            first, last = self.fade_out
            level *= 0.0 if last <= first else max(0.0, 1.0 - (frame - first) / (last - first))
        return level


def music_now(timeline: "Timeline", frame: float) -> list:
    """`[(MusicPlayed, seconds into it)]` playing at `frame`, the event's track first, then any tune."""
    out = []
    for played in timeline.music:
        if played.start <= frame and (played.end is None or frame < played.end):
            out.append((played, (frame - played.start) / FRAMES_A_SECOND))
    out.sort(key=lambda item: item[0].slot == 0)
    return out


@dataclass
class Timeline:
    """A script played out: when each instruction and node starts, how long
    it all takes, and what each frame shows (`at`)."""
    frames: int
    starts: list                       # each instruction's start frame
    node_starts: list
    node_ends: list
    problems: dict                     # {instruction index: [words]}
    units: dict                        # {unit id: SceneUnit}
    tracks: dict
    camera_moves: list
    first_camera: Optional[Camera]
    boxes: list                        # [(open, close, BoxShown, [(frame, line, portrait)])]
    screens: list                      # [(start, end, from rgba, to rgba)]
    screen_start: tuple
    map_number: Optional[int] = None
    changes_map: list = field(default_factory=list)   # [(frame, map number)]
    waits_for_button: dict = field(default_factory=dict)   # {instruction index: frames}
    #: The map's colour changes (ColorField): `[(start, end, from, to)]` (`colour_change`).
    field_colours: list = field(default_factory=list)
    #: Captions (the remaster's E7): `[(start, end, Caption key)]`.
    captions: list = field(default_factory=list)
    #: The music played (`MusicPlayed`), in order; the event's two tracks (PlayStation music ids, 0: none).
    music: list = field(default_factory=list)
    music_tracks: tuple = (0, 0)
    #: Whether its units march as it starts (`starts_marching`).
    marching: bool = False

    def node_at(self, frame: float) -> int:
        """The node playing at `frame`: the last to have started."""
        found = 0
        for index, start in enumerate(self.node_starts):
            if start <= frame:
                found = index
            else:
                break
        return found

    def at(self, frame: float) -> Frame:
        frame = max(0.0, min(float(frame), float(self.frames)))
        units = [_pose_at(track, frame) for track in self.tracks.values()]
        camera = _camera_at(self.first_camera, self.camera_moves, frame)
        boxes = []
        for opened, closed, box, changes in self.boxes:
            if opened <= frame < closed:
                shown = replace(box)
                for when, line, portrait in changes:
                    if when <= frame:
                        shown.line = line
                        if portrait is not None:
                            shown.portrait = portrait
                boxes.append(shown)
        screen = self.screen_start
        for start, end, before, after in self.screens:
            if frame >= start:
                t = 1.0 if end <= start else min(1.0, (frame - start) / (end - start))
                screen = tuple(before[i] + (after[i] - before[i]) * t for i in range(4))
        number = self.map_number
        for when, changed in self.changes_map:
            if when <= frame:
                number = changed
        caption = None
        for start, end, key in self.captions:
            if start <= frame < end:
                caption = CaptionShown(key, frame - start, end - frame)
        return Frame(int(frame), units, camera, boxes, screen, number, _changes_at(self.field_colours, frame),
                     caption)


def _ease(t: float, curve: int) -> float:
    """A move's progress: straight for curve mode 0, eased in and out otherwise."""
    t = max(0.0, min(1.0, t))
    if curve & 3 == 0:
        return t
    return t * t * (3.0 - 2.0 * t)


def _camera_at(first: Optional[Camera], moves: list, frame: float) -> Optional[Camera]:
    camera = replace(first) if first is not None else None
    for start, end, before, after, curve in moves:
        if frame < start:
            break
        t = 1.0 if end <= start else _ease((frame - start) / (end - start), curve)
        values = [b + (a - b) * t for b, a in zip(before.values(), after.values())]
        camera = Camera(*values)
    return camera


def _facing_between(a: float, b: float, t: float, mode: int = 0) -> float:
    """A turn from sixteenth `a` to `b`, the short way round, `t` of the way."""
    delta = (b - a) % 16.0
    if delta > 8.0:
        delta -= 16.0
    return (a + delta * t) % 16.0


def _pose_at(track: _Track, frame: float) -> Pose:
    pose = replace(track.start)
    for when, kind, data in track.changes:
        if when > frame:
            break
        if kind == "set":
            for name, value in data.items():
                setattr(pose, name, value)
        elif kind == "walk":
            path, per_tile = data["path"], data["per_tile"]
            steps = len(path) - 1
            done = (frame - when) / per_tile if per_tile > 0 else steps
            if done >= steps:
                end = path[-1]
                pose.x, pose.y, pose.level = float(end[0]), float(end[1]), end[2]
                pose.walking = False
                if steps:
                    pose.facing = data["last_facing"]
                pose.animation, pose.since = data.get("after_animation"), int(when + steps * per_tile)
            else:
                step = int(done)
                a, b = path[step], path[step + 1]
                part = done - step
                pose.x = a[0] + (b[0] - a[0]) * part
                pose.y = a[1] + (b[1] - a[1]) * part
                pose.level = b[2] if part > 0.5 else a[2]
                pose.facing = float(_facing_of_step(a, b))
                pose.walking = True
                pose.animation, pose.since = data.get("animation"), int(when)
        elif kind == "turn":
            start, end = when, data["end"]
            t = 1.0 if end <= start else min(1.0, (frame - start) / (end - start))
            pose.facing = _facing_between(data["from"], data["to"], t)
        elif kind == "fade":
            end = data["end"]
            t = 1.0 if end <= when else min(1.0, (frame - when) / (end - when))
            pose.alpha = data["from"] + (data["to"] - data["from"]) * t
            if data["to"] <= 0.0 and t >= 1.0:
                pose.shown = False
        elif kind == "colour":
            end = data["end"]
            t = 1.0 if end <= when else min(1.0, (frame - when) / (end - when))
            pose.tint = blend_change(data["from"], data["to"], t)
        elif kind == "lift":
            end = data["end"]
            t = 1.0 if end <= when else min(1.0, (frame - when) / (end - when))
            pose.lift = tuple(data["from"][i] + (data["to"][i] - data["from"][i]) * t for i in range(3))
    return pose


def _facing_of_step(a, b) -> int:
    """The sixteenth a unit faces walking from tile `a` to tile `b`."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    if abs(dx) >= abs(dy):
        return 12 if dx > 0 else 4
    return 8 if dy > 0 else 0


def walk_path(start: tuple, goal: tuple, tiles: Optional[set] = None) -> list:
    """
    The tiles a unit walks through from `start` to `goal` (`(x, y, level)`),
    both included: the shortest way over `tiles` (`{(x, y)}`, the map's) when
    given and the goal is on it, else along x and then y.
    """
    sx, sy, sl = int(round(start[0])), int(round(start[1])), start[2]
    gx, gy, gl = goal
    if (sx, sy) == (gx, gy):
        return [(sx, sy, sl), (gx, gy, gl)] if sl != gl else [(sx, sy, sl)]
    if tiles and (gx, gy) in tiles and (sx, sy) in tiles:
        seen = {(sx, sy): None}
        queue = deque([(sx, sy)])
        while queue:
            here = queue.popleft()
            if here == (gx, gy):
                break
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                there = (here[0] + dx, here[1] + dy)
                if there in tiles and there not in seen:
                    seen[there] = here
                    queue.append(there)
        if (gx, gy) in seen:
            back, at = [], (gx, gy)
            while at is not None:
                back.append(at)
                at = seen[at]
            back.reverse()
            return [(x, y, sl) for x, y in back[:-1]] + [(gx, gy, gl)]
    path = [(sx, sy, sl)]
    x, y = sx, sy
    while x != gx:
        x += 1 if gx > x else -1
        path.append((x, y, sl))
    while y != gy:
        y += 1 if gy > y else -1
        path.append((x, y, sl))
    path[-1] = (gx, gy, gl)
    return path


#: A walk's speed when the script gives none (the game's usual 0x800).
DEFAULT_WALK_SPEED = 0x800
#: A world tile is 28 units across; the camera's numbers are four times the world's.
TILE_UNITS, CAMERA_SCALE = 28.0, 4.0
#: Focus aims this many world units below the two units' feet (down is more:
#: the decompilation's `script_focus` adds 0x20 to each unit's height), and
#: higher by these when its first unit is Altima's second form (73) or its
#: second her first form (65).
FOCUS_BELOW = 0x20
FOCUS_HIGHER_FIRST, FOCUS_HIGHER_SECOND = {73: -0x50}, {65: -0x20}
#: Frames a turn takes a sixteenth at each speed (the decompilation's table).
TURN_FRAMES = (4, 2, 1, 0)
#: How long a teleport's fade takes, and a unit's colour change when none is given.
TELEPORT_FRAMES = 24


def button_frames(words: str) -> int:
    """How long the preview gives a box before its button is pressed: time to read the words."""
    return int(FRAMES_A_SECOND * 1.5 + 3 * len(words or ""))


def frames_per_tile(speed: int) -> float:
    """Frames a walk takes a tile: the game moves a walking unit speed / 4,096 world units a 60th of a
    second (the step's direction normalised, scaled by the frame interval and the speed)."""
    speed = speed if speed and speed > 0 else DEFAULT_WALK_SPEED
    return TILE_UNITS * 4096.0 / speed


def default_ground(x: float, y: float, level: int) -> tuple:
    """A tile's middle in the game's world units (x, height, y) when no map says how high it is."""
    return (x * TILE_UNITS + TILE_UNITS / 2, 0.0, y * TILE_UNITS + TILE_UNITS / 2)


class _Player:
    """Plays a script's instructions out (see `play`)."""

    def __init__(self, script: Script, units: dict, words: Callable, ground: Callable,
                 tiles: Optional[set], map_number: Optional[int], marching: bool = False,
                 music: tuple = (0, 0)):
        self.script, self.mode = script, script.mode
        self.units, self.words = units, words
        self.ground, self.tiles = ground, tiles
        self.items = script.instructions
        self.starts = [0] * len(self.items)
        self.problems: dict = {}
        self.tracks = {}
        #: A battle under way: its units march; a scene's stand (`starts_marching`).
        self.marching = marching
        start_animation = None if marching else STAND
        for unit_id, unit in units.items():
            self.tracks[unit_id] = _Track(Pose(unit_id, float(unit.x), float(unit.y), unit.level,
                                               float((unit.facing & 3) * 4), unit.shown,
                                               animation=start_animation))
        #: WalkToAnim's animations, by unit, for the walk they wait for (0x79).
        self.after_walk: dict = {}
        #: When InflictStatus's threads end (0x92), which WaitForInstruction 67 waits for.
        self.status_end = 0
        #: The map's colour changes, and the colours kept (StoreModifiedMapPalette, 0x66).
        self.field_colours, self.field_kept = [], None
        #: Captions: `[start, end, key]`, ended by the next.
        self.captions = []
        #: The event's two tracks (0: none), the one playing (0 or 1, the
        #: decompilation's `g_sound_current_music_track_index`), and what plays.
        self.music_tracks = [int(music[0]) if music else 0, int(music[1]) if music and len(music) > 1 else 0]
        self.music_index = 0
        self.music: list = []
        if self.music_tracks[0]:
            self.music.append(MusicPlayed(self.music_tracks[0], 0.0, slot=1))
        #: When each unit's walk, turn and sprite move end; the cameras', screens' and boxes'.
        self.walks_end, self.turns_end, self.lifts_end = {}, {}, {}
        self.camera_moves, self.first_camera = [], None
        self.boxes, self.open_boxes = [], {}
        self.screens = []
        has_map_in = any(i.opcode == 0x4D for i in self.items)
        self.screen_start = (0.0, 0.0, 0.0, 1.0) if has_map_in else (0.0, 0.0, 0.0, 0.0)
        self.screen_end_frame = 0
        self.block_ends, self.effect_end = [], 0
        self.map_number, self.changes_map = map_number, []
        self.curve = 0
        self.waits_for_button = {}
        self.end_frame = 0
        #: The block of the event animations' file each slot holds (LoadEVTCHR).
        self.evtchr_slots = {0: None, 1: None}

    # -- helpers ---------------------------------------------------------------------

    def problem(self, index: int, words: str) -> None:
        self.problems.setdefault(index, []).append(words)

    def track(self, unit_id: int, index: int) -> Optional[_Track]:
        found = self.tracks.get(unit_id)
        if found is None and unit_id not in PARTY_UNITS and unit_id not in SELECTOR_UNITS \
                and unit_id != EVERY_UNIT:
            self.problem(index, f"unit {unit_id}")
        return found

    def group(self, unit_id: int, index: int) -> list:
        """The units a unit group names: one, every unit, or a team (all, here)."""
        if unit_id == EVERY_UNIT or unit_id in TEAM_GROUPS:
            return list(self.tracks.values())
        found = self.track(unit_id, index)
        return [found] if found is not None else []

    def pose(self, track: _Track, frame: float) -> Pose:
        return _pose_at(track, frame)

    def camera_now(self, frame: float) -> Camera:
        return _camera_at(self.first_camera, self.camera_moves, frame) or Camera()

    def add(self, track: _Track, frame: float, kind: str, data) -> None:
        track.changes.append((frame, kind, data))
        track.changes.sort(key=lambda c: c[0])

    def turn(self, track: _Track, frame: float, to: float, speed: int, delay: int = 0) -> float:
        start = frame + delay
        now = self.pose(track, start).facing
        delta = abs(((to - now) % 16.0 + 8.0) % 16.0 - 8.0)
        per = TURN_FRAMES[speed] if 0 <= speed < len(TURN_FRAMES) else TURN_FRAMES[1]
        end = start + delta * per
        self.add(track, start, "turn", {"from": now, "to": float(to) % 16.0, "end": end})
        self.turns_end[track.start.unit_id] = max(self.turns_end.get(track.start.unit_id, 0), end)
        return end

    def facing_towards(self, a: Pose, bx: float, by: float) -> int:
        dx, dy = bx - a.x, by - a.y
        if abs(dx) < 1e-6 and abs(dy) < 1e-6:
            return int(a.facing)
        if abs(dx) >= abs(dy):
            return 12 if dx > 0 else 4
        return 8 if dy > 0 else 0

    # -- running ---------------------------------------------------------------------

    def run(self) -> int:
        end = self.thread(0, len(self.items), 0)
        ends = [end, *self.block_ends, *self.walks_end.values(), *self.turns_end.values(),
                *self.lifts_end.values(), self.screen_end_frame, self.effect_end]
        ends += [m[1] for m in self.camera_moves]
        self.end_frame = max(ends) if ends else 0
        # A caption ends where the next begins, if that is sooner.
        self.captions.sort(key=lambda c: c[0])
        for this, after in zip(self.captions, self.captions[1:]):
            this[1] = min(this[1], after[0])
        for opened, closed, box, changes in self.boxes:
            if closed is None:
                pass
        self.boxes = [(o, c if c is not None else self.end_frame + 1, b, ch) for o, c, b, ch in self.boxes]
        return self.end_frame

    def thread(self, first: int, last: int, frame: float) -> float:
        """Runs instructions `first` to `last` from `frame`; the frame it finishes at."""
        i = first
        jumped_to = None
        while i < last:
            item = self.items[i]
            op = item.opcode
            self.starts[i] = int(frame)
            if jumped_to is not None:
                if op in FORWARD_TARGETS and item.operands[:1] == bytes([jumped_to]):
                    jumped_to = None
                i += 1
                continue
            if op in (0x2A, 0x1D, 0x49):
                closing = {0x2A: 0x2B, 0x1D: 0x1E, 0x49: 0x4A}[op]
                end = _matching_end(self.items, i, op, closing)
                if end is None or end >= last:
                    i += 1
                    continue
                if op == 0x1D:
                    # A camera path: its cameras one after another from here.
                    finished = self.thread(i + 1, end, frame)
                    self.block_ends.append(finished)
                else:
                    finished = self.thread(i + 1, end, frame)
                    self.block_ends.append(finished)
                self.starts[end] = int(frame)
                i = end + 1
                continue
            if op == END or op == 0xE3:
                self.starts[i] = int(frame)
                for j in range(i + 1, last):
                    self.starts[j] = int(frame)
                return frame
            if op == 0xD1:
                jumped_to = item.operands[0]
                i += 1
                continue
            if op == 0xD4:
                # Reached in order (its jump not taken): the script ends here in the game.
                for j in range(i + 1, last):
                    self.starts[j] = int(frame)
                return frame
            frame = self.step(i, item, frame)
            i += 1
        return frame

    def step(self, index: int, item: Instruction, frame: float) -> float:
        """Plays one instruction from `frame`; the frame the thread goes on at."""
        op, mode = item.opcode, self.mode
        v = operands(item, mode)
        if op == 0xF1:
            return frame + max(0, v["frames"])
        if op == 0xE5:
            task = v["task"]
            if task == TASK_MESSAGE:
                return self.wait_for_boxes(index, frame)
            if task == TASK_CAMERA:
                ends = [m[1] for m in self.camera_moves if m[0] <= frame]
                return max([frame] + ends)
            if task == TASK_BLOCK:
                return max([frame] + [e for e in self.block_ends])
            if task == TASK_SCREEN or task in (TASK_DARKNESS, TASK_LIGHT):
                return max(frame, self.screen_end_frame)
            if task == TASK_SPRITE_MOVE:
                return max([frame] + list(self.lifts_end.values()))
            if task == TASK_STATUS:
                return max(frame, self.status_end)
            return frame
        if op == 0x16:
            frames = FRAMES_A_SECOND
            self.waits_for_button[index] = frames
            return frame + frames
        if op == 0x10:
            self.open_box(index, item, v, frame)
            return frame
        if op == 0x51:
            self.change_box(index, v, frame)
            return frame
        if op == 0x19:
            self.camera(index, v, frame)
            return frame
        if op == 0x1F:
            self.focus(index, item, v, frame)
            return frame
        if op == 0x63:
            self.curve = v["curve"]
            return frame
        if op == 0x4D:
            frames = max(1, v["frames"])
            self.screens.append((frame, frame + frames, (0.0, 0.0, 0.0, 1.0), (0.0, 0.0, 0.0, 0.0)))
            self.screen_end_frame = max(self.screen_end_frame, frame + frames)
            return frame
        if op == 0x3E:
            frames = max(1, v["frames"])
            before = (v["red"] / 255.0, v["green"] / 255.0, v["blue"] / 255.0)
            after = (v["end_red"] / 255.0, v["end_green"] / 255.0, v["end_blue"] / 255.0)
            # Towards black or white darkens or lightens the screen; any
            # other colour tints it. Alpha follows how far the colour is from
            # the screen's own (none).
            self.screens.append((frame, frame + frames, (*before, _strength(before, v["style"])),
                                 (*after, _strength(after, v["style"]))))
            self.screen_end_frame = max(self.screen_end_frame, frame + frames)
            return frame
        if op in (0x4C, 0x13):
            self.changes_map.append((frame, v["map"]))
            return frame
        if op == 0x5F:
            track = self.track(v["unit"], index)
            if track is not None:
                self.add(track, frame, "set", {"x": float(v["x"]), "y": float(v["y"]), "level": v["level"] & 1,
                                               "facing": float((v["facing"] & 3) * 4), "walking": False})
                if self.tiles is not None and (v["x"], v["y"]) not in self.tiles:
                    self.problem(index, "tile")
            return frame
        if op == 0x45:
            track = self.track(v["unit"], index)
            if track is not None:
                self.add(track, frame, "set", {"shown": not v["hidden"], "alpha": 1.0})
            return frame
        if op == 0x47:
            unit_id = v["unit"]
            if unit_id not in self.tracks:
                self.units[unit_id] = SceneUnit(unit_id, 0, 0, 0, v["x"], v["y"], v["level"] & 1,
                                                v["facing"] & 3, False, None, 0, v["sprite"])
                self.tracks[unit_id] = _Track(Pose(unit_id, float(v["x"]), float(v["y"]), v["level"] & 1,
                                                   float((v["facing"] & 3) * 4), False, animation=STAND))
            self.add(self.tracks[unit_id], frame, "set", {"shown": not v["hidden"], "alpha": 1.0})
            return frame
        if op == 0x44:
            # Drawn; a teleport's fade, started just before, goes on.
            track = self.track(v["unit"], index)
            if track is not None:
                self.add(track, frame, "set", {"shown": True})
            return frame
        if op in (0x46, 0x3D, 0x99):
            track = self.track(v["unit"], index)
            if track is not None:
                self.add(track, frame, "set", {"shown": False})
            return frame
        if op == 0x98:
            track = self.track(v["unit"], index)
            if track is not None:
                self.add(track, frame, "set", {"shown": True, "alpha": 0.0})
                self.add(track, frame, "fade", {"from": 0.0, "to": 1.0, "end": frame + TELEPORT_FRAMES})
                self.effect_end = max(self.effect_end, frame + TELEPORT_FRAMES)
            return frame
        if op == 0x94:
            track = self.track(v["unit"], index)
            if track is not None:
                self.add(track, frame, "fade", {"from": 1.0, "to": 0.0, "end": frame + TELEPORT_FRAMES})
                self.effect_end = max(self.effect_end, frame + TELEPORT_FRAMES)
            return frame
        if op == 0x28:
            self.walk(index, v, frame)
            return frame
        if op == 0x79:
            # WalkToAnim: the animation the unit takes when its walk ends (the
            # decompilation's `g_unit_pending_animation_ids`, set as it stops),
            # its walk under way or the next; without one it marches.
            track = self.track(v["unit"], index)
            if track is not None:
                for when, kind, data in reversed(track.changes):
                    if kind == "walk" and when <= frame <= when + (len(data["path"]) - 1) * data["per_tile"]:
                        data["after_animation"] = v["animation"]
                        break
                else:
                    self.after_walk[v["unit"]] = v["animation"]
            return frame
        if op == 0x29:
            return max(frame, self.walks_end.get(v["unit"], frame))
        if op == 0x39:
            return max([frame] + list(self.walks_end.values()))
        if op == 0x2D:
            for n, track in enumerate(self.group(v["unit"], index)):
                facing = v["facing"]
                now = self.pose(track, frame).facing
                if 0x11 <= facing < 0x14:
                    to = (now + (facing & 0xF) * 4) % 16
                elif facing in (0x10, 0x14):
                    to = now if facing == 0x10 else (self.units[track.start.unit_id].facing & 3) * 4
                else:
                    to = facing & 0xF
                self.turn(track, frame, to, v["speed"], v["delay"] * (n + 1) // 4)
            return frame
        if op in (0x53, 0x2C):
            target = self.track(v["unit"], index)
            if target is not None:
                there = self.pose(target, frame)
                for track in self.group(v["unit2"], index):
                    if track is target:
                        continue
                    here = self.pose(track, frame)
                    self.turn(track, frame, self.facing_towards(here, there.x, there.y), v["speed"])
                    if op == 0x2C:
                        self.turn(target, frame, self.facing_towards(there, here.x, here.y), v["speed"])
            return frame
        if op == 0x69:
            for track in self.group(v["unit"], index):
                here = self.pose(track, frame)
                self.turn(track, frame, self.facing_towards(here, v["x"], v["y"]), v["speed"])
            return frame
        if op == 0x64:
            return max(frame, self.turns_end.get(v["unit"], frame))
        if op == 0x65:
            return max([frame] + list(self.turns_end.values()))
        if op == 0x11:
            # An animation from 500 is a sequence of a slot's block (`unit_sprites`): the one there now.
            slot = 1 if v["animation"] >= EVTCHR_ANIMATIONS[1] else 0 if v["animation"] >= EVTCHR_ANIMATIONS[0] \
                else None
            block = self.evtchr_slots.get(slot) if slot is not None else None
            for track in self.group(v["unit"], index):
                self.add(track, frame, "set", {"animation": v["animation"], "since": int(frame), "evtchr": block})
            return frame
        if op == 0x58:
            self.evtchr_slots[v["slot"] & 1] = v["block"]
            return frame
        if op in (0x5A, 0x5B):
            self.evtchr_slots[v["slot"] & 1] = None
            return frame
        if op == 0x7F:
            block = self.evtchr_slots.get(v["slot"] & 1)
            track = self.track(v["unit"], index)
            if track is not None and block is not None:
                self.add(track, frame, "set", {"colours": (block, v["palette"] & 15)})
            return frame
        if op == 0x8C:
            track = self.track(v["unit"], index)
            if track is not None:
                self.add(track, frame, "set", {"facing": float((v["facing"] & 3) * 4),
                                               "animation": v["animation"] & 0xFF, "since": int(frame)})
            return frame
        if op == 0x80:
            # March: each unit of the group marches (its status animation),
            # the script waiting its frames after each (`script_opcode_80_march`).
            for track in self.group(v["unit"], index):
                self.add(track, frame, "set", {"animation": None, "since": int(frame)})
                frame += max(0, v["frames"] or 0)
            return frame
        if op == 0x32:
            # ColorUnit: a unit's colours, as ColorField the map's (`colour_change`).
            if v["style"] is None:
                return frame
            ends = frame + colour_frames(v["frames"] or 0)
            for track in self.group(v["unit"], index):
                now = self.pose(track, frame).tint
                to = colour_change(v["style"], v["red"], v["green"], v["blue"], now, None)
                self.add(track, frame, "colour", {"from": now, "to": to, "end": ends})
            return frame
        if op == 0x33:
            if v["style"] is None:
                return frame
            now = _changes_at(self.field_colours, frame)
            to = colour_change(v["style"], v["red"], v["green"], v["blue"], now, self.field_kept)
            self.field_colours.append((frame, frame + colour_frames(v["frames"] or 0), now, to))
            return frame
        if op == 0x66:
            # StoreModifiedMapPalette: the map's colours now are those kept.
            self.field_kept = _changes_at(self.field_colours, frame)
            return frame
        if op == 0xE7:
            if v["caption"] is not None:
                self.captions.append([frame, frame + CAPTION_FRAMES, v["caption"]])
            return frame
        if op == 0x22:
            self.switch_music(frame, v)
            return frame
        if op == 0x60:
            # FadeSound: the music goes over the frames, doubled for each of the first operand.
            for played in self.music:
                if played.slot and played.end is None and played.fade_out is None:
                    played.fade_out = (frame, frame + ((v["frames"] or 0) << min(8, v["shift"] or 0)))
            return frame
        if op == 0x5E:
            # EndTrack: the music stops, and the track of the slot named is let go.
            self.stop_music(frame)
            if v["slot"] in (1, 2):
                self.music_tracks[v["slot"] - 1] = 0
            return frame
        if op == 0x84:
            if v.get("tune"):
                self.music.append(MusicPlayed(TUNE_BASE + v["tune"], float(frame), slot=0))
            return frame
        if op == 0x43 and v["function"] == CALL_ALTIMA_MUSIC:
            self.stop_music(frame)
            self.music.append(MusicPlayed(ALTIMA_MUSIC, float(frame), slot=1))
            return frame
        if op == 0x3B:
            track = self.track(v["unit"], index)
            if track is not None:
                now = self.pose(track, frame).lift
                to = (float(v["dx"]), float(v["dy"]), float(v["dz"]))
                end = frame + max(0, v["frames"])
                self.add(track, frame, "lift", {"from": now, "to": to, "end": end})
                self.lifts_end[v["unit"]] = max(self.lifts_end.get(v["unit"], 0), end)
            return frame
        if op == 0x6F:
            return max(frame, self.lifts_end.get(v["unit"], frame))
        if op == 0x92:
            # InflictStatus (`script_inflict_status_thread`, run beside the
            # script): 0 on a unit that lives makes it stand (a battle's
            # speakers stop marching so), 2 (poison) kneel; WaitForInstruction
            # 67 waits for its frames.
            track = self.track(v["unit"], index)
            if track is not None and v["status"] in (0, 2):
                self.add(track, frame, "set", {"animation": STAND if v["status"] == 0 else KNEEL,
                                               "since": int(frame)})
            self.status_end = max(self.status_end, frame + max(0, v["frames"] or 0))
            return frame
        return frame

    def stop_music(self, frame: float) -> None:
        """The event's music stops (a tune goes on)."""
        for played in self.music:
            if played.slot and played.end is None:
                played.end = float(frame)

    def switch_music(self, frame: float, v: dict) -> None:
        """
        SwitchTrack: the music stops and the event's other track begins, if it
        has one, at the volume given and coming in over the frames given (the
        decompilation's `event_frame.c`: the request's value isn't read, the
        two tracks take turns).
        """
        self.stop_music(frame)
        self.music_index ^= 1
        track = self.music_tracks[self.music_index]
        if track:
            volume = v["volume"] or 0
            loud = min(volume, MUSIC_VOLUME_MOST) / MUSIC_VOLUME_MOST
            self.music.append(MusicPlayed(track, float(frame), volume=loud, fade_in=float(v["fade"] or 0),
                                          slot=self.music_index + 1))

    def walk(self, index: int, v: dict, frame: float) -> None:
        track = self.track(v["unit"], index)
        if track is None:
            return
        goal = (v["x"], v["y"], v["level"] & 1)
        if self.tiles is not None and (goal[0], goal[1]) not in self.tiles:
            self.problem(index, "tile")
        here = self.pose(track, frame)
        path = walk_path((here.x, here.y, here.level), goal, self.tiles)
        per_tile = frames_per_tile(v["speed"])
        steps = len(path) - 1
        last = _facing_of_step(path[-2], path[-1]) if steps else int(here.facing)
        # When it arrives it marches (the game settles a unit on its tile in
        # its status animation, `move_settle_on_tile`), unless WalkToAnim
        # (0x79) gave it another.
        self.add(track, frame, "walk", {"path": path, "per_tile": per_tile, "last_facing": float(last),
                                        "animation": None, "after_animation": self.after_walk.pop(v["unit"], None)})
        self.walks_end[v["unit"]] = frame + steps * per_tile

    def camera(self, index: int, v: dict, frame: float) -> None:
        now = self.camera_now(frame)
        values = list(now.values())
        for n, name in enumerate(("x", "height", "y", "tilt", "yaw", "roll", "zoom")):
            if v[name] != KEEP:
                values[n] = float(v[name])
        # A yaw goes the short way round from the camera's.
        if v["yaw"] != KEEP:
            delta = (values[4] - now.yaw) % 4096.0
            if delta > 2048.0:
                delta -= 4096.0
            values[4] = now.yaw + delta
        target = Camera(*values)
        frames = max(0, v["frames"])
        if self.first_camera is None and not self.camera_moves:
            self.first_camera = Camera(*target.values()) if frames <= 1 else Camera(*now.values())
        self.camera_moves.append((frame, frame + frames, now, target, self.curve))

    def focus(self, index: int, item: Instruction, v: dict, frame: float) -> None:
        """
        Focus aims the next CAMERA at the middle of two units, a little below
        their feet (the decompilation's `script_focus`: `FOCUS_BELOW`, and
        higher at Altima's two forms). Aimed at their feet, as the first
        build did, half of the game's cameras looked 32 units too high (Zodi,
        19 October, event 008: "maybe the camera is not matching the right
        framing").
        """
        a, b = self.track(v["unit"], index), self.track(v["unit2"], index)
        nxt = next((j for j in range(index + 1, len(self.items)) if self.items[j].opcode == 0x19), None)
        if a is None or b is None or nxt is None:
            return
        pa, pb = self.pose(a, frame), self.pose(b, frame)
        wa = self.ground(pa.x, pa.y, pa.level)
        wb = self.ground(pb.x, pb.y, pb.level)
        below = FOCUS_BELOW + FOCUS_HIGHER_FIRST.get(v["unit"], 0) + FOCUS_HIGHER_SECOND.get(v["unit2"], 0)
        values = {"x": int((wa[0] + wb[0]) / 2 * CAMERA_SCALE),
                  "height": int(((wa[1] + wb[1]) / 2 + below) * CAMERA_SCALE),
                  "y": int((wa[2] + wb[2]) / 2 * CAMERA_SCALE)}
        camera = self.items[nxt]
        try:
            self.items[nxt] = with_operands(camera, self.mode, **values)
        except ScriptError:
            return

    def open_box(self, index: int, item: Instruction, v: dict, frame: float) -> None:
        window = v["box"] & 3
        old = self.open_boxes.pop(window, None)
        if old is not None:
            self.boxes[old] = (self.boxes[old][0], frame, *self.boxes[old][2:])
        box = BoxShown(window, v["line"], v["unit"], v["box"], v["portrait"], v["dx"], v["dy"], v["arrow"],
                       v["options"], int(frame), index)
        self.boxes.append((frame, None, box, []))
        self.open_boxes[window] = len(self.boxes) - 1
        if v["unit"] not in self.tracks and v["unit"] not in PARTY_UNITS and v["unit"] not in SELECTOR_UNITS \
                and points_at_speaker(v["box"]):
            self.problem(index, f"unit {v['unit']}")
        if self.words(v["line"]) is None:
            self.problem(index, "line")

    def change_box(self, index: int, v: dict, frame: float) -> None:
        window = v["box"] & 3
        at = self.open_boxes.get(window)
        if v["line"] == CLOSE_BOX[self.mode]:
            if at is not None:
                self.open_boxes.pop(window)
                self.boxes[at] = (self.boxes[at][0], frame, *self.boxes[at][2:])
            return
        if at is None:
            self.problem(index, "no box")
            return
        self.boxes[at][3].append((frame, v["line"], v["portrait"] or None))
        if self.words(v["line"]) is None:
            self.problem(index, "line")

    def wait_for_boxes(self, index: int, frame: float) -> float:
        """A wait for the message: the preview's button press, after time to read the words open."""
        newest = None
        for at in self.open_boxes.values():
            opened, _closed, box, changes = self.boxes[at]
            line = changes[-1][1] if changes else box.line
            when = changes[-1][0] if changes else opened
            if newest is None or when > newest[0]:
                newest = (when, at, line)
        if newest is None:
            return frame
        when, at, line = newest
        pressed = max(frame, when + button_frames(self.words(line) or ""))
        self.waits_for_button[index] = int(pressed - frame)
        opened, _closed, box, changes = self.boxes[at]
        if not box.box & 0x80:
            # Closed by the button unless it was opened to be closed later.
            self.boxes[at] = (opened, pressed, box, changes)
            for window, place in list(self.open_boxes.items()):
                if place == at:
                    self.open_boxes.pop(window)
        return pressed


def _strength(colour: tuple, mode: int) -> float:
    """How much of the screen a colour screen covers: none for black when lightening, all of black
    when darkening (the game blends; the preview lays the colour over the map)."""
    brightness = max(colour) if colour else 0.0
    if mode & 1:
        return brightness
    return 1.0 - brightness if max(colour) - min(colour) < 0.05 else 0.6


def starts_marching(script: Script) -> bool:
    """
    Whether an event begins with its units marching: a battle under way, as
    a script shows by standing its speakers before they speak
    (InflictStatus, 0x92) or setting them marching again at its end (March,
    0x80). A scene's units stand as the game makes them (a unit's first
    sequence is its standing one, `animation_update_unit_wep_eff`), and so do
    the units of a battle before it starts; the player's deployed units march
    (the page says so for a scenario with squads).
    """
    return any(item.opcode in (0x80, 0x92) for item in script.instructions)


def play(script: Script, units: dict, words: Callable[[int], Optional[str]] = lambda line: None,
         ground: Callable = default_ground, tiles: Optional[set] = None,
         map_number: Optional[int] = None, marching: Optional[bool] = None,
         music: tuple = (0, 0)) -> Timeline:
    """
    `script` played out: each instruction's frame, each node's, and what
    every frame shows. `units` are the scene's (`scene_units`), `words(line)`
    a line's words (None when the scene's text hasn't it), `ground(x, y,
    level)` a tile's middle in world units and `tiles` the map's `(x, y)`,
    when a map is shown. `marching`: whether its units march as it starts
    (None: as `starts_marching` says); `music`: the event's two tracks
    (`scenario_music`), the first playing from its start.
    """
    copy = Script(script.mode, list(script.instructions), script.tail, script.stopped)
    marching = starts_marching(script) if marching is None else bool(marching)
    player = _Player(copy, {k: replace(u) for k, u in units.items()}, words, ground, tiles, map_number,
                     marching, music)
    frames = player.run()
    nodes = group_nodes(script)
    node_starts = [player.starts[node.first] if node.count else 0 for node in nodes]
    node_ends = []
    for n, node in enumerate(nodes):
        node_ends.append(node_starts[n + 1] if n + 1 < len(nodes) else frames)
    return Timeline(int(frames), player.starts, node_starts, node_ends, player.problems, player.units,
                    player.tracks, player.camera_moves, player.first_camera, player.boxes, player.screens,
                    player.screen_start, map_number, player.changes_map, player.waits_for_button,
                    player.field_colours, [tuple(c) for c in player.captions], player.music,
                    (int(music[0]) if music else 0, int(music[1]) if music and len(music) > 1 else 0), marching)
