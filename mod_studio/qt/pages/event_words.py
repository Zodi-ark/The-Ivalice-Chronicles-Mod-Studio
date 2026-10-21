"""
The Event Editor's words: what each node is called and says, what each
field is called, and the nodes and ready-made events the node list offers.

Kept apart from the drawing so a check can read every sentence the page
can show (the dash rule: no " - " in any of them, Zodi's) and so the words
for one instruction are in one place. What an instruction does is the
engine's (`event_scripts`); this is how the page says it.

The rules the words follow: plain words, no symbols; a name where the game
gives one (a unit's, a map's, a line's words) and the number where it
doesn't; never a name guessed for an instruction nobody has worked out,
which is shown as its number and its bytes.
"""
from __future__ import annotations

import html
import re
from dataclasses import dataclass, field
from typing import Callable, Optional

from ... import event_scripts as es

#: The kinds, in the node list's order (the engine's).
KINDS = es.KINDS
#: Each kind's heading in the node list and its color (the node's band):
#: the second mock-up's, measured off `event_editor2.png`.
KIND_NAMES = {"talk": "Talk", "units": "Units", "camera": "Camera", "screen": "Screen", "sound": "Sound",
              "wait": "Wait", "story": "Story", "other": "Other"}
KIND_COLOURS = {"talk": "#d8b662", "units": "#4fb3a9", "camera": "#5b9bd5", "screen": "#e0a253",
                "sound": "#b18ad8", "wait": "#8a8f98", "story": "#e8705f", "other": "#7d8089"}
#: A unit walking or turning has a band of its own, as in the mock-up: WALK
#: and TURN in green, among the Units' nodes.
MOVE_COLOUR = "#6bbf73"
#: The node list's entries drawn in MOVE_COLOUR, and the opcodes whose node's band says TURN.
MOVE_ENTRIES = ("walk", "turn", "face")
TURN_OPCODES = (0x2D, 0x53)


def band_words(script: es.Script, node: es.Node) -> tuple:
    """`(label, color)`: what a node's band says and its color. A speech node
    says SPEAK, a walk WALK and a turn TURN, as the mock-up's do; any other
    says its kind."""
    if node.kind == "talk":
        return "SPEAK", KIND_COLOURS["talk"]
    first = script.instructions[node.first].opcode
    if node.shape == "walk" or first == 0x28:
        return "WALK", MOVE_COLOUR
    if node.shape in ("turn", "turns") or first in TURN_OPCODES:
        return "TURN", MOVE_COLOUR
    return KIND_NAMES.get(node.kind, node.kind).upper(), KIND_COLOURS.get(node.kind, KIND_COLOURS["other"])


def entry_colour(key: str, kind: str) -> str:
    """The color of an entry of the node list: its kind's, or green for walking and turning."""
    return MOVE_COLOUR if key in MOVE_ENTRIES else KIND_COLOURS.get(kind, KIND_COLOURS["other"])


# =============================================================================
# The marks in a line's words
# =============================================================================
# A scene's line can carry marks in < >, which the game reads and never shows
# (Zodi, 19 October, with event 045 in the game beside the page): its
# `<speaker="Lord Dycedarg Beoulve">` is the name over the box, `<stoplip>`
# stops the face's mouth, and WotL Restoration's lines put words in <i>
# italics </i>. Any other mark is taken out of the words the same way.

#: Any mark, and the two that say something.
_MARK = re.compile(r"<[^<>]*>")
_SPEAKER = re.compile(r"""^<\s*speaker\s*=\s*["']([^"']*)["']\s*/?>$""", re.I)
_STOP_LIPS = re.compile(r"^<\s*stoplip\s*/?>$", re.I)
_ITALIC = re.compile(r"^<\s*(/?)\s*i\s*>$", re.I)


@dataclass
class Spoken:
    """A line's words as the box shows them."""
    words: str = ""                     # what the box says, every mark taken out
    rich: str = ""                      # the same as rich text, italics kept
    name: Optional[str] = None          # the name a speaker mark gives the box
    lips_until: Optional[int] = None    # letters spoken before a stoplip mark, if it has one
    runs: tuple = ()                    # the words in pieces: ((words, italic), ...), as the game's font draws them


def spoken(text: Optional[str]) -> Spoken:
    """`text` without its marks (see above), and what they said."""
    text = str(text or "")
    words, rich, name, lips_until, runs = [], [], None, None, []
    at = 0
    italic = False
    for mark in _MARK.finditer(text):
        piece = text[at:mark.start()]
        words.append(piece)
        rich.append(html.escape(piece))
        if piece:
            runs.append((piece, italic))
        at = mark.end()
        found = _SPEAKER.match(mark.group(0))
        if found:
            name = found.group(1).strip() or name
            continue
        if _STOP_LIPS.match(mark.group(0)):
            if lips_until is None:
                lips_until = len("".join(words))
            continue
        found = _ITALIC.match(mark.group(0))
        if found:
            closing = bool(found.group(1))
            if closing and italic:
                rich.append("</i>")
                italic = False
            elif not closing and not italic:
                rich.append("<i>")
                italic = True
    piece = text[at:]
    words.append(piece)
    rich.append(html.escape(piece))
    if piece:
        runs.append((piece, italic))
    if italic:
        rich.append("</i>")
    plain = "".join(words)
    return Spoken(plain, "".join(rich).replace("\n", "<br>"), name, lips_until, tuple(runs))


def shown_words(text: Optional[str]) -> Optional[str]:
    """A line's words without its marks, None staying None (a line the scene hasn't)."""
    return None if text is None else spoken(text).words


FACINGS = {0: "south", 1: "west", 2: "north", 3: "east"}
SIXTEENTHS = {0: "south", 2: "south west", 4: "west", 6: "north west", 8: "north", 10: "north east",
              12: "east", 14: "south east"}
#: WaitForInstruction's tasks, as a person would say what is waited for.
TASKS = {1: "Until a button", 4: "Until the camera stops", 6: "Until the map's darkness is done",
         7: "Until the map's light is done", 8: "Until the units moving together are done",
         11: "Until the sprite has moved", 12: "Until the screen's color is done",
         52: "Until the event's pictures are read", 54: "Until the dark screen is done",
         56: "Until the battle's conditions are shown", 61: "Until the picture is shown",
         65: "Until the effect is done", 67: "Until the status is done"}
WINDOWS = {0: "where the game puts it", 1: "above the speaker", 2: "below the speaker", 3: "in the middle"}
#: Where a box of the kind placed by facing (0x70, most in battles) goes.
FACING_WHERE = "above or below as the speaker faces the camera"
#: The colour screen's change: the PlayStation's notes don't name its modes, so they are numbers.
SECONDS_NAMES = {}


def seconds(frames: float) -> str:
    """Frames as a person says them: "at once", "1 second", "0.8 seconds"."""
    if frames <= 1:
        return "at once"
    value = frames / es.FRAMES_A_SECOND
    text = f"{value:.1f}".rstrip("0").rstrip(".")
    return f"{text} second" if text == "1" else f"{text} seconds"


def facing_words(value: int) -> str:
    return FACINGS.get(value & 3, str(value))


def sixteenth_words(value: int) -> str:
    if value == 0x10:
        return "the camera"
    if 0x11 <= value <= 0x13:
        turns = value & 0xF
        return {1: "a quarter turn more", 2: "a half turn more", 3: "three quarter turns more"}[turns]
    if value == 0x14:
        return "the way it first faced"
    value &= 0xF
    return SIXTEENTHS.get(value, f"{value} sixteenths of a turn from south")


def box_words(box: int) -> str:
    """A DisplayMessage's box type in words: its kind, where, its arrow."""
    kind = (box >> 4) & 7
    if box & 0x70 == es.FACING_KIND:
        parts = ["Speech box", FACING_WHERE]
    else:
        parts = ["Speech box" if kind == 1 else f"Box kind {kind}", WINDOWS[box & 3]]
    if box & 0x04:
        parts.append("as a thought")
    if box & 0x08:
        parts.append("with no arrow")
    if box & 0x80:
        parts.append("open until closed")
    return ", ".join(parts)


@dataclass
class Scene:
    """What the words name things by: the scene's units, its lines, its maps,
    and the music: the piece a music instruction starts as the event plays
    (`music(instruction)`, an `event_scripts.MusicPlayed` or None) and the
    pieces' names (`event_scripts.music_titles`)."""
    unit_names: dict = field(default_factory=dict)          # {unit id: name}
    words: Callable[[int], Optional[str]] = lambda line: None
    speaker: Callable[[int], Optional[str]] = lambda line: None
    map_names: dict = field(default_factory=dict)
    music: Callable = lambda item: None
    music_titles: dict = field(default_factory=dict)

    def piece(self, item) -> str:
        """The piece a music instruction starts, named: "Hall of Worship (music 51)", or ""."""
        played = self.music(item)
        if played is None:
            return ""
        title = str(self.music_titles.get(played.track) or "").strip()
        number, dot, rest = title.partition(". ")
        if dot and number.isdigit() and rest.strip():
            title = rest.strip()
        return f"{title} (music {played.track})" if title else f"Music {played.track}"

    def unit(self, unit_id: int) -> str:
        if unit_id == es.EVERY_UNIT:
            return "Everyone"
        if unit_id in es.PARTY_UNITS:
            return f"Party member {unit_id - es.PARTY_UNITS.start + 1}"
        if unit_id in es.TEAM_GROUPS:
            return f"Team {unit_id - es.TEAM_GROUPS.start}"
        return self.unit_names.get(unit_id) or f"Unit {unit_id}"

    def line(self, line: int, mode: str = "enhanced") -> str:
        """A line's words as the box shows them: its marks taken out (`spoken`)."""
        if line == es.CLOSE_BOX[mode]:
            return ""
        found = self.words(line)
        return shown_words(found) if found is not None else f"Line {line}"


def _first_line(text: str, most: int = 60) -> str:
    text = " ".join(str(text or "").split())
    return text if len(text) <= most else text[:most - 3].rstrip() + "..."


def instruction_words(item: es.Instruction, scene: Scene, mode: str = "enhanced") -> tuple:
    """`(title, detail)` for one instruction."""
    op = item.opcode
    v = es.operands(item, mode)
    u = lambda name="unit": scene.unit(v[name])                       # noqa: E731
    if op == 0x10:
        unit = v["unit"]
        speaker = scene.speaker(v["line"])
        who = speaker or (scene.unit(unit) if unit in scene.unit_names else None)
        title = f"{who} speaks" if who and not v["box"] & 0x08 else (f"{who}, unseen" if who else "A voice")
        return title, _first_line(scene.line(v["line"], mode))
    if op == 0x51:
        if v["line"] == es.CLOSE_BOX[mode]:
            return "Close the box", f"The box {WINDOWS[v['box'] & 3]}"
        return "Change the words", _first_line(scene.line(v["line"], mode))
    if op == 0xEB:
        return "Next page", _first_line(scene.line(v["line"], mode))
    if op == 0xC2:
        return "A line", _first_line(scene.line(v["line"], mode))
    if op == 0xF1:
        return "Wait", seconds(v["frames"])
    if op == 0xE5:
        return TASKS.get(v["task"], f"Until task {v['task']} is done"), ""
    if op == 0x16:
        return "Until a button", "The player presses a button"
    if op == 0x29:
        return f"Until {u()} arrives", ""
    if op == 0x64:
        return f"Until {u()} has turned", ""
    if op == 0x65:
        return "Until everyone has turned", ""
    if op == 0x39:
        return "Until everyone has stopped", ""
    if op == 0x6F:
        return f"Until {u()} has moved", ""
    if op == 0x48:
        return "Until the unit is added", ""
    if op == 0x4B:
        return "Until the units are added", ""
    if op == 0x12:
        return f"Until {u()} is ready", ""
    if op == 0x5F:
        return f"Place {u()}", f"At {v['x']}, {v['y']}{', upper level' if v['level'] & 1 else ''}, " \
                               f"facing {facing_words(v['facing'])}"
    if op == 0x45:
        return f"Add {u()}", "Hidden until shown" if v["hidden"] else "Shown"
    if op == 0x47:
        return f"Add a sprite as unit {v['unit']}", f"Sprite {v['sprite']} at {v['x']}, {v['y']}"
    if op == 0x44:
        return f"Show {u()}", ""
    if op == 0x46:
        return f"Hide {u()}", ""
    if op == 0x3D:
        return f"Remove {u()}", ""
    if op == 0x99:
        return f"Remove {u()} from the battle", ""
    if op == 0x98:
        return f"{u()} appears", "Teleports in"
    if op == 0x94:
        return f"{u()} vanishes", "Teleports out"
    if op == 0x28:
        return f"{u()} walks", f"To {v['x']}, {v['y']}{', upper level' if v['level'] & 1 else ''}"
    if op == 0x79:
        return f"{u()} walks in a pose", f"Animation {v['animation']}"
    if op == 0x2D:
        return f"{u()} turns", f"To face {sixteenth_words(v['facing'])}"
    if op == 0x53:
        return f"{u('unit2')} faces {u()}", ""
    if op == 0x2C:
        return f"{u()} and {u('unit2')} face each other", ""
    if op == 0x69:
        return f"{u()} faces a tile", f"Tile {v['x']}, {v['y']}"
    if op == 0x11:
        return f"{u()}'s pose", f"Animation {v['animation']}"
    if op == 0x8C:
        return f"{u()} turns and poses", f"Facing {facing_words(v['facing'])}, animation {v['animation'] & 0xFF}"
    if op == 0x80:
        return f"{u()} waits", "Standing as in battle"
    if op == 0x32:
        if not (v["red"] or v["green"] or v["blue"]):
            return f"{u()}'s own colors", seconds(v["frames"])
        return f"Color {u()}", f"Red {v['red']}, green {v['green']}, blue {v['blue']}"
    if op == 0x3B:
        return f"Move {u()}'s sprite", f"By {v['dx']}, {v['dy']}, {v['dz']} over {seconds(v['frames'])}"
    if op == 0x70:
        return f"{u()} jumps", f"{max(0, v['length'] - 1)} tiles"
    if op == 0x92:
        return f"A status on {u()}", f"Kind {v['status']}"
    if op == 0x83:
        return f"Change {u()}'s stats", f"Stat {v['stat']} by {v['delta']}"
    if op == 0x86:
        return f"Give {u()} a weapon to hold", f"Item {v['item']}"
    if op == 0x87:
        return f"{u('unit2')} shoots {u()}", ""
    if op == 0x68:
        return f"Mirror {u()}'s sprite" if v["flag"] == 1 else f"{u()}'s sprite unmirrored", ""
    if op == 0x19:
        return "Camera", seconds(v["frames"]) if v["frames"] > 1 else "At once"
    if op == 0x1F:
        return "Camera on units", f"{u()} and {u('unit2')}" if v["unit"] != v["unit2"] else u()
    if op == 0x63:
        return "Camera's easing", f"Curve {v['curve']}"
    if op == 0x38:
        return "Camera's speed", seconds(v["speed"])
    if op == 0x73:
        return "Camera moves by", ""
    if op == 0x41:
        return "Earthquake", ""
    if op == 0x42:
        return "Earthquake stops", ""
    if op == 0x4D:
        return "Map comes in", f"Over {v['frames']} frames"
    if op == 0x3E:
        return "Screen color", f"Over {seconds(v['frames'])}"
    if op == 0x1A:
        return "Map darkness", seconds(v["frames"])
    if op == 0x1B:
        return "Map light", seconds(v["frames"])
    if op == 0x2E:
        return "Background colors", ""
    if op == 0x4F:
        return "Time of day", f"Kind {v['time']}"
    if op == 0x3C:
        return "Weather", f"Kind {v['weather'] & 0xF}"
    if op == 0x18:
        return "Effect", f"Effect {v['effect']} on {scene.unit(v['target'])}"
    if op == 0x91:
        return "The map's name", ""
    if op == 0x21:
        return "Sound effect", str(v["sound"])
    if op == 0x22:
        # The game takes turns between the event's two tracks (the number isn't read).
        played = scene.music(item)
        if played is None:
            return "Music", "The event's other track"
        return "Music", f"Track {played.slot}: {scene.piece(item)}"
    if op == 0x7C:
        return "Stop the sounds", ""
    if op == 0x5E:
        return "Stop the music", (f"And let go of track {v['slot']}" if v["slot"] in (1, 2) else "")
    if op == 0x60:
        fade = (v["frames"] or 0) << min(8, v["shift"] or 0)
        return "Fade the music out", f"Over {seconds(fade)}" if fade > 1 else "At once"
    if op == 0x84:
        return "A tune", scene.piece(item) or f"Music {es.TUNE_BASE + (v['tune'] or 0)}"
    if op in (0x4C, 0x13):
        name = scene.map_names.get(v["map"], "")
        return "Change the map", f"To map {v['map']:03d}{' ' + name if name else ''}"
    if op == 0x2A:
        return "Together", "What follows runs at the same time"
    if op == 0x2B:
        return "End of together", ""
    if op == 0x1D:
        return "Camera path", ""
    if op == 0x1E:
        return "End of camera path", ""
    if op == 0x49:
        return "Add units together", ""
    if op == 0x4A:
        return "End of adding units", ""
    if op == es.END:
        return "The end", "The event ends here"
    if op == 0xE3:
        return "The end", ""
    if op == 0xD0:
        return "If the last test failed", f"Go to mark {v['target']}"
    if op == 0xD1:
        return "Go to mark", str(v["target"])
    if op in (0xD2, 0xD4):
        return "Mark", str(v["target"])
    if op == 0xD3:
        return "Go back to mark", str(v["target"])
    if op == 0xD5:
        return "Mark to go back to", str(v["target"])
    if 0xA0 <= op <= 0xA5:
        return "Test the two variables", ""
    if op == 0xBE:
        return "Clear story variable", str(v["variable"])
    if 0xB0 <= op <= 0xBD:
        verbs = {0: "Add", 2: "Take away", 4: "Multiply", 6: "Divide", 8: "Remainder of", 10: "And",
                 12: "Or"}
        verb = verbs.get((op - 0xB0) & 0xE, "Change")
        source = f"variable {v['value']}" if op & 1 else str(v["value"])
        return "Story variable", f"{verb} {source}, variable {v['variable']}"
    if op == 0x43:
        if v["function"] == es.CALL_ALTIMA_MUSIC:
            return "Altima's music", scene.piece(item) or f"Music {es.ALTIMA_MUSIC}"
        return "A function of the game", str(v["function"])
    if op == 0x78:
        return "Show the battle's conditions", f"Kind {v['display']}"
    if op == 0x1C:
        return "Event speed", str(v["speed"])
    if op == 0x7E:
        return "Until a variable is a value", f"Variable {v['variable']} is {v['value']}"
    if op == 0x82:
        return "Read the battle's pictures", ""
    if op in (0xF0, 0xF2):
        return "Nothing", ""
    # Known instructions whose work isn't drawn in the preview: named as the
    # PlayStation decompilation names them, in words.
    known = {
        0x58: "Read pictures for the event", 0x59: "Keep the event's pictures",
        0x5A: "Let the kept pictures go", 0x5B: "Let the read pictures go",
        0x5C: "Keep a unit's picture aside", 0x5D: "Let a kept picture go",
        0x6C: "Units' colors follow the light again", 0x6D: "Units' colors held",
        0x7F: "A unit in the event's pictures", 0x4E: "A unit's shadow", 0x8A: "The effect starts",
        0x8B: "The effect plays", 0x88: "The map moves again", 0x89: "The map held still",
        0x76: "The screen darkens", 0x77: "The dark screen goes", 0x7D: "A picture on the screen",
        0x8E: "Until the picture is shown", 0x8F: "Menus locked", 0x93: "Days pass",
        0x96: "The map's next state", 0x97: "A unit's own colors again", 0x27: "The map as it was",
        0x50: "Portraits read", 0x25: "Two speakers", 0x26: "A box waiting goes on",
        0x37: "The portrait turned", 0x31: "The background's color", 0x33: "The ground's color",
        0x66: "The map's colors kept", 0x6A: "A background sound changes", 0x6B: "A background sound",
        0x54: "A 3D object's state", 0x55: "A ground object's state", 0x56: "Until the 3D object is done",
        0x57: "Until the ground object is done", 0x71: "The first unit", 0x72: "Pause for debugging",
        0x7A: "A unit leaves the party", 0x7B: "Until a button is held", 0x81: "Units' move effects",
        0x85: "A date unlocked", 0x90: "A tutorial's cursor", 0x95: "Nothing",
        0x3A: "Until the files are read", 0x3F: "A tile the camera can't see through",
        0x40: "A tile's height", 0x62: "A battle unit placed", 0xC0: "A camera turned off",
        0xD8: "Nothing", 0xD9: "Marks before this aren't gone back to", 0xDA: "Nothing", 0xDC: "Nothing",
        0xE0: "Nothing", 0x17: "Nothing", 0x23: "Nothing", 0x24: "Nothing", 0x61: "Nothing",
        0x74: "Nothing", 0x75: "Nothing",
    }
    if op in known:
        return known[op], " ".join(str(b) for b in item.operands)
    # The rest: the opcode's number and its bytes, as nothing says more.
    return f"Instruction {op:02X}", " ".join(f"{b}" for b in item.operands) if item.operands else ""


def node_words(script: es.Script, node: es.Node, scene: Scene) -> tuple:
    """`(title, detail)` for a node: its group's words, or its one instruction's."""
    items = es.node_instructions(script, node)
    mode = script.mode
    first = items[0]
    if node.shape in ("speak", "words"):
        return instruction_words(first, scene, mode)
    if node.shape == "add_units":
        added = [i for i in items if i.opcode == 0x45]
        names = [scene.unit(es.operand(i, "unit", mode)) for i in added]
        hidden = all(es.operand(i, "hidden", mode) for i in added)
        if len(added) == 1:
            return f"Add {names[0]}", "Hidden until shown" if hidden else "Shown"
        more = f"{names[0]} and {len(names) - 1} more"
        return f"Add {len(added)} units", more + (", hidden" if hidden else "")
    if node.shape == "camera":
        camera = next(i for i in items if i.opcode == 0x19)
        frames = es.operand(camera, "frames", mode)
        focus = next((i for i in items if i.opcode == 0x1F), None)
        detail = seconds(frames) if frames > 1 else "At once"
        if focus is not None:
            a, b = es.operand(focus, "unit", mode), es.operand(focus, "unit2", mode)
            return f"Camera on {scene.unit(a)}" + (f" and {scene.unit(b)}" if a != b else ""), detail
        return "Camera", detail
    if node.shape == "camera_path":
        cameras = [i for i in items if i.opcode == 0x19]
        total = sum(max(0, es.operand(i, "frames", mode)) for i in cameras)
        return "Camera path", f"{len(cameras)} moves, {seconds(total)}"
    if node.shape == "together":
        inside = len(items) - 2
        return "Together", f"{inside} instruction{'s' if inside != 1 else ''} at the same time"
    if node.shape == "add_together":
        added = [i for i in items if i.opcode == 0x45]
        return f"Add {len(added)} units together", ""
    if node.shape == "walk":
        return instruction_words(first, scene, mode)
    if node.shape in ("turns", "turn"):
        turns = [i for i in items if i.opcode == 0x2D]
        who = scene.unit(es.operand(turns[0], "unit", mode))
        if len(turns) > 1:
            return f"{who} looks round", f"{len(turns)} turns"
        return f"{who} turns", f"To face {sixteenth_words(es.operand(turns[0], 'facing', mode))}"
    if node.shape == "appear":
        return instruction_words(first, scene, mode)
    return instruction_words(first, scene, mode)


def node_problem(node: es.Node, timeline: Optional[es.Timeline], scene: Scene) -> str:
    """What is wrong with a node, in words (the red line under it), or ""."""
    if timeline is None:
        return ""
    found = []
    for index in node.indexes():
        for problem in timeline.problems.get(index, []):
            if problem == "tile":
                found.append("Pick a tile on the map")
            elif problem == "line":
                found.append("Its words aren't in the scene's text")
            elif problem == "no box":
                found.append("No box is open for these words")
            elif problem.startswith("unit "):
                found.append(f"Unit {problem.split()[1]} isn't in this scene")
    return found[0] if found else ""


# =============================================================================
# Fields
# =============================================================================

#: What each operand is called on the big node, by its name in the engine's layout.
FIELD_LABELS = {
    "unit": "Who", "unit2": "And who", "line": "What they say", "box": "Box", "portrait": "Portrait",
    "dx": "Move the box across", "dy": "Up or down", "arrow": "Move the arrow across",
    "options": "How the box opens", "last": "Last byte", "thread": "Thread",
    "x": "Across (x)", "y": "Along (y)", "level": "Upper level", "facing": "Facing",
    "speed": "Speed", "terrain": "Mind the ground", "frames": "Frames", "animation": "Animation",
    "keep_facing": "Keep facing", "height": "Height", "tilt": "Tilt", "yaw": "Turn", "roll": "Roll",
    "zoom": "Zoom", "hidden": "Hidden", "sound": "Sound", "track": "Track", "volume": "Volume",
    "fade": "Fade", "map": "Map", "style": "Mode", "red": "Red", "green": "Green", "blue": "Blue",
    "end_red": "Red at the end", "end_green": "Green at the end", "end_blue": "Blue at the end",
    "delay": "Delay", "curve": "Curve", "task": "Waits for", "target": "Mark", "variable": "Variable",
    "value": "Value", "sprite": "Sprite", "effect": "Effect", "status": "Status", "stat": "Stat",
    "delta": "By", "item": "Item", "flag": "On", "keep_yaw": "Keep the turn", "weather": "Weather",
    "time": "Time of day", "function": "Function", "display": "Display", "row": "Row",
    "next_line": "Next line", "more": "More", "length": "Length", "direction": "Direction",
    "step": "Step", "period": "Period", "step2": "Second step", "period2": "Second period",
    "target_mode": "Target mode", "slot": "Slot", "shift": "Shift", "tune": "Tune", "dz": "Height move",
    "weight": "Weight", "unused": "Unused", "store": "Keep", "angle_x": "Angle x", "angle_y": "Angle y",
    "angle_z": "Angle z", "scale_x": "Scale x", "scale_y": "Scale y", "scale_z": "Scale z",
    "top_red": "Top red", "top_green": "Top green", "top_blue": "Top blue", "bottom_red": "Bottom red",
    "bottom_green": "Bottom green", "bottom_blue": "Bottom blue", "target_x": "Target x",
}
#: Field labels where one instruction needs its own.
OWN_LABELS = {(0x51, "box"): "Which box", (0x19, "x"): "Look at across", (0x19, "y"): "Look at along",
              (0x19, "height"): "Look at height", (0x73, "x"): "Across", (0x2D, "facing"): "To face",
              (0x8C, "facing"): "Facing", (0xEB, "line"): "This page"}


def field_label(opcode: int, name: str) -> str:
    return OWN_LABELS.get((opcode, name)) or FIELD_LABELS.get(name) or name.replace("_", " ").capitalize()


# =============================================================================
# The node list and the ready-made events
# =============================================================================

@dataclass(frozen=True)
class Entry:
    """One entry of the node list: what it is called, what it does, its kind, and how to make it."""
    key: str
    title: str
    blurb: str
    kind: str


ENTRIES = (
    Entry("speak", "Speak", "A speech box over a unit, with their words", "talk"),
    Entry("words", "Change the words", "New words in the open box, without closing it", "talk"),
    Entry("close", "Close the box", "Takes the speech box away", "talk"),
    Entry("place", "Place a unit", "Puts a unit on a tile, facing a way", "units"),
    Entry("walk", "Walk", "A unit walks to a tile, and the event waits for it", "units"),
    Entry("turn", "Turn", "A unit turns to face a way", "units"),
    Entry("face", "Face a unit", "A unit turns to face another", "units"),
    Entry("pose", "Pose", "A unit plays one of its animations", "units"),
    Entry("add", "Add a unit", "Brings one of the battle's units onto the map", "units"),
    Entry("show", "Show a unit", "Draws a unit that is hidden", "units"),
    Entry("hide", "Hide a unit", "Stops drawing a unit", "units"),
    Entry("teleport_in", "Teleport in", "A unit appears with the teleport's shimmer", "units"),
    Entry("teleport_out", "Teleport out", "A unit vanishes with the teleport's shimmer", "units"),
    Entry("camera", "Camera", "The camera looks at a place, over a time", "camera"),
    Entry("camera_on", "Camera on a unit", "The camera looks at a unit", "camera"),
    Entry("camera_path", "Camera path", "Two camera moves played one after the other", "camera"),
    Entry("map_in", "Map comes in", "The map appears out of black", "screen"),
    Entry("fade_out", "Fade to black", "The screen goes black over a second", "screen"),
    Entry("fade_in", "Fade from black", "The screen comes back from black", "screen"),
    Entry("sound", "Sound effect", "Plays one of the game's sounds", "sound"),
    Entry("music", "Music", "Starts a piece of music", "sound"),
    Entry("stop_sounds", "Stop the sounds", "Stops every sound effect", "sound"),
    Entry("wait", "Wait", "Waits half a second, or as long as you set", "wait"),
    Entry("button", "Until a button", "Waits for the player to press a button", "wait"),
    Entry("until_camera", "Until the camera stops", "Waits for the camera's move to finish", "wait"),
    Entry("until_arrives", "Until a unit arrives", "Waits for a unit's walk to finish", "wait"),
    Entry("together", "Together", "The nodes put inside it run at the same time", "story"),
    Entry("change_map", "Change the map", "Moves the event to another map", "story"),
)
FAVOURITES = ("speak", "walk", "wait", "camera")


@dataclass(frozen=True)
class ReadyMade:
    key: str
    title: str
    blurb: str
    entries: tuple


READY_MADE = (
    ReadyMade("talk", "Two units talk", "One speaks, the other answers, and the boxes close",
              ("speak", "speak_other", "close")),
    ReadyMade("walk_in", "Someone walks in and speaks", "A unit is shown, walks to a tile, faces the "
              "first unit and speaks", ("show_other", "walk_other", "face", "speak_other")),
    ReadyMade("opening", "The scene opens", "The camera finds the first unit as the map comes in",
              ("camera_on", "map_in", "wait")),
    ReadyMade("ending", "The scene ends", "The screen fades to black and waits", ("fade_out", "wait")),
)


def build_entry(key: str, lengths: es.Lengths, mode: str, units: list, new_line: Callable[[], int],
                tile: tuple = (0, 0)) -> list:
    """
    The instructions an entry of the node list makes, for a scene whose
    units are `units` (their ids, the first is who speaks first) and whose
    next new line is `new_line()`. A unit left to pick is the first.
    """
    first = units[0] if units else 0
    other = units[1] if len(units) > 1 else first
    make = lambda op, **v: es.make(op, lengths, mode, **v)        # noqa: E731
    box = 0x10 | 1
    if key in ("speak", "speak_other"):
        who = first if key == "speak" else other
        return [make(0x10, thread=0x10, box=box, line=new_line(), unit=who), make(0xE5, task=es.TASK_MESSAGE)]
    if key == "words":
        return [make(0x51, box=1, line=new_line()), make(0xE5, task=es.TASK_MESSAGE)]
    if key == "close":
        return [make(0x51, box=1, line=es.CLOSE_BOX[mode]), make(0xE5, task=es.TASK_MESSAGE)]
    if key == "place":
        return [make(0x5F, unit=first, x=tile[0], y=tile[1])]
    if key in ("walk", "walk_other"):
        who = first if key == "walk" else other
        return [make(0x28, unit=who, x=tile[0], y=tile[1], speed=es.DEFAULT_WALK_SPEED, terrain=1),
                make(0x29, unit=who)]
    if key == "turn":
        return [make(0x2D, unit=first, facing=8, style=0, speed=1), make(0x64, unit=first)]
    if key == "face":
        return [make(0x53, unit=first, unit2=other, speed=1), make(0x64, unit=other)]
    if key == "pose":
        return [make(0x11, unit=first, animation=2)]
    if key == "add":
        return [make(0x45, unit=first, hidden=0), make(0x48)]
    if key in ("show", "show_other"):
        return [make(0x44, unit=first if key == "show" else other)]
    if key == "hide":
        return [make(0x46, unit=first)]
    if key == "teleport_in":
        return [make(0x98, unit=first), make(0x44, unit=first)]
    if key == "teleport_out":
        return [make(0x94, unit=first)]
    if key == "camera":
        return [make(0x19, x=tile[0] * 112 + 56, height=0, y=tile[1] * 112 + 56, tilt=420, yaw=es.KEEP,
                     roll=0, zoom=4096, frames=60), make(0xE5, task=es.TASK_CAMERA)]
    if key == "camera_on":
        return [make(0x1F, unit=first, unit2=first, keep_yaw=1),
                make(0x19, x=0, height=0, y=0, tilt=420, yaw=es.KEEP, roll=0, zoom=4096, frames=60),
                make(0xE5, task=es.TASK_CAMERA)]
    if key == "camera_path":
        return [make(0x1D),
                make(0x19, x=es.KEEP, height=es.KEEP, y=es.KEEP, tilt=es.KEEP, yaw=es.KEEP, roll=es.KEEP,
                     zoom=3600, frames=60),
                make(0x19, x=es.KEEP, height=es.KEEP, y=es.KEEP, tilt=es.KEEP, yaw=es.KEEP, roll=es.KEEP,
                     zoom=4096, frames=60),
                make(0x1E), make(0xE5, task=es.TASK_CAMERA)]
    if key == "map_in":
        return [make(0x4D, frames=64)]
    if key == "fade_out":
        return [make(0x3E, style=0, red=0, green=0, blue=0, end_red=0, end_green=0, end_blue=0, frames=60),
                make(0xE5, task=es.TASK_SCREEN)]
    if key == "fade_in":
        return [make(0x3E, style=0, red=0, green=0, blue=0, end_red=255, end_green=255, end_blue=255,
                     frames=60), make(0xE5, task=es.TASK_SCREEN)]
    if key == "sound":
        return [make(0x21, sound=0x41)]
    if key == "music":
        return [make(0x22, track=1, volume=127, fade=0)]
    if key == "stop_sounds":
        return [make(0x7C)]
    if key == "wait":
        return [make(0xF1, frames=30)]
    if key == "button":
        return [make(0x16)]
    if key == "until_camera":
        return [make(0xE5, task=es.TASK_CAMERA)]
    if key == "until_arrives":
        return [make(0x29, unit=first)]
    if key == "together":
        return [make(0x2A), make(0x2B)]
    if key == "change_map":
        return [make(0x4C, map=1)]
    raise KeyError(key)


def entry_by_key(key: str) -> Optional[Entry]:
    return next((e for e in ENTRIES if e.key == key), None)


def all_sentences() -> list:
    """Every fixed sentence the page shows from here, for the dash check."""
    out = [k for k in KIND_NAMES.values()] + list(TASKS.values()) + list(WINDOWS.values())
    out += list(FIELD_LABELS.values()) + list(OWN_LABELS.values())
    for entry in ENTRIES:
        out += [entry.title, entry.blurb]
    for ready in READY_MADE:
        out += [ready.title, ready.blurb]
    return out
