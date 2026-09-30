"""
The game's UI layout files (`.uib`) and texture part lists (`.utexpt`):
reading them, and changing their numbers where they already are.

A `.uib` is one screen, or a set of reusable pieces of screen - "components"
- each a tree of boxes on a 1920x1080 canvas. A box has a position, a size,
a scale, the texture piece it shows or the text settings it uses, and the
component's timelines hold short animations that set those values again as
a screen opens, closes or changes state. A `.utexpt` is a texture sheet's
cutting list: the name and rectangle of each piece. The game has 252 layouts
under `ui/`, 2,215 part lists and 3,109 UI textures.

**Why numbers are changed in place, never re-written.** FF16Tools reads the
same file format for Final Fantasy XVI, and it was the reference for the byte
layout here (Nenkai, MIT, commit dd91fb4). On The Ivalice Chronicles' files
it reads none of the 252 as shipped - each component record carries two
fields at 0x20/0x24 where FF16 has padding - and, patched to read them,
writes none of them back unchanged. Sixteen of the twenty-four animation
step types in use are not understood by anyone yet (4,514 of 56,877 steps).
Overwriting a four-byte number where it already sits needs none of that
understanding, keeps every byte nobody understands exactly as it was, and
was confirmed in the game: an edited layout loads from a mod and shows the
edit exactly as written.

**A move carries the box's position keys.** 1,281 of the 1,317 boxes with
position keys (timeline element 5002) have their resting position among
those keys - the Rumors screen's details panel sits at (744,170) and its
`HomePosition`, `Show` and `Hide` keys say 744,170 too. Change only the
origin and the `Show` animation puts it back. So a move shifts the origin
and every position key targeting that box, in its component, by the same
amount; the other 36 are particles and map markers whose paths shift the
same way. Scale keys (5004) are scaled by the same ratio, for the same
reason (654 of 676), and so are size keys (5003: 121 of the 122 boxes that
have them rest at a size among them - a grow-in from 0 stays a grow-in from
0). An axis resting at 0 has no ratio, and its keys are left as they are.

**Opacity and colour keys follow too, each its own way.** 3,709 of the 3,737
boxes with opacity keys (5009) rest at a value among them (to 0.0001 - 3,654
exactly, the others a float's last digit apart), so a new resting opacity
scales every opacity key by the same ratio, as a resize does: a fade in from
0 to 1 becomes a fade in from 0 to the new value, steps between keep their
place in it, and none goes above 1. A box resting at 0 (1,594 of them -
hidden until an animation shows it) has no ratio, and its keys are left as
they are. Colour
keys (5007) are different: 428 of the 429 boxes with them rest at a colour
among them, but only 660 of the 1,233 keys restate it - the rest are other
states' colours, a highlight under the cursor or the red of a cost that can't
be paid. So a new colour replaces the keys that equal the old resting colour,
all four bytes, and leaves the others as they are.

**Animation keys can be edited directly too, in place**: a key's start frame
and length (in its 0x20-byte record, at +0x0C and +0x10) and its easing and
value (in its data block, at +0x30 and +0x74). None is added or removed.
An edit names its key by component, animation and place in the animation,
and is checked against the key's kind, box and start frame when applied;
it must keep the key inside its animation and in order among its box's keys
of that kind (all 6,533 tracks of several keys in the game play in strictly
rising frames). Written after
the boxes' edits, a key edited directly keeps the value it was given when
its box is moved or resized as well: the edit is its final value. Easing
kinds (1 the commonest, then 4, 22, 2 ...) are numbers nobody has decoded;
they are written as given. The 18 kinds of step whose values are not read
here (5,154 of the 56,877 steps) are not edited.

**A colour is four bytes: red, green, blue, alpha, in that order** - the
order of the colour keys. For all 227 boxes whose red and blue differ and
whose resting colour is among their keys, it matches them in file order and
never with red and blue swapped. Which byte is red is read from what the
colours look like (brown text on the tavern's parchment, gold glows); it has
not been checked in the game yet.

The figures above were measured on Zodi's copies of all 252 files; the
research that produced them, and the tools to re-run it, are in
`dev/research/uib/`.

Nothing here imports Qt.
"""
from __future__ import annotations

import math
import struct
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

MAGIC = b"UIB\0"
VERSION = 10

#: Where a layout's own files live under the unpacked game folder.
LAYOUT_ROOT = "ui"
LAYOUT_EXTENSION = ".uib"

NODE_KINDS = {
    1: "Layer", 2: "Image", 3: "Text", 4: "Ninegrid", 5: "Counter", 6: "Rect",
    7: "Ellipse", 8: "Bezier", 9: "Collision", 10: "Reference", 11: "Effect",
    12: "Model", 13: "Mask",
}
COMPONENT_KINDS = {
    1: "Root", 2: "Custom", 3: "Button", 4: "CheckBox", 5: "RadioButton",
    6: "Tab", 7: "Slider", 8: "ScrollBar", 9: "List", 10: "ListItem",
    11: "DropdownList", 12: "Gauge", 13: "TextBoard", 14: "Window",
    15: "BahamutEffect",
}

#: A component's blend mode, as FF16Tools names them. In the game's files:
#: normal 2,075 components, colour dodge 109, linear dodge 107, multiply 44,
#: overlay 20 (the screen filters), screen 7.
BLEND_MODES = {
    0: "normal", 1: "darken", 2: "multiply", 3: "colour burn", 4: "linear burn",
    5: "lighten", 6: "screen", 7: "colour dodge", 8: "linear dodge", 9: "overlay",
    10: "soft light", 11: "hard light", 12: "vivid light", 13: "linear light",
}

#: Timeline element types whose meaning was measured from their values.
KEY_POSITION = 5002      # two ints, x and y
KEY_SIZE = 5003          # two ints, width and height
KEY_SCALE = 5004         # two floats
KEY_COLOUR = 5007        # four bytes, R G B A
KEY_OPACITY = 5009       # one float, 0-1
KEY_CHILD_TIMELINE = 5028  # plays a child component's timeline, by name

#: Timeline target type naming a box in the component by name.
TARGET_COMPONENT_BOX = 4001

#: What an animation key's value is, for the kinds whose value is read here
#: - each written where it sits, in the key's data block.
KEY_VALUE_FORMATS = {KEY_POSITION: "<ii", KEY_SIZE: "<ii", KEY_SCALE: "<ff",
                     KEY_COLOUR: "<4B", KEY_OPACITY: "<f"}
#: Kinds whose keys can be edited: those, and a child animation's start and
#: length (its value is the child's name, which is not edited in place).
EDITABLE_KEY_KINDS = frozenset(KEY_VALUE_FORMATS) | {KEY_CHILD_TIMELINE}
#: The entry of one screen's edits that holds its animation key edits,
#: beside the boxes' - `{"@animation": {key id: key edit}}`. No box key can
#: be it: a box key always has a "/" in it.
ANIMATION_KEYS = "@animation"

#: What can be edited, and the kinds of box each applies to.
FIELD_ORIGIN = "origin"
FIELD_SIZE = "size"
FIELD_SCALE = "scale"
FIELD_FONT_SIZE = "font_size"
FIELD_COLOUR = "colour"       # four ints 0-255: red, green, blue, alpha
FIELD_OPACITY = "opacity"     # a float, 0-1
EDITABLE_FIELDS = (FIELD_ORIGIN, FIELD_SIZE, FIELD_SCALE, FIELD_FONT_SIZE,
                   FIELD_COLOUR, FIELD_OPACITY)
#: The fields whose edit also changes the animation keys that restate them.
KEYED_FIELDS = {FIELD_ORIGIN: KEY_POSITION, FIELD_SIZE: KEY_SIZE, FIELD_SCALE: KEY_SCALE,
                FIELD_COLOUR: KEY_COLOUR, FIELD_OPACITY: KEY_OPACITY}

# Node base (0x70 bytes). Offsets from the node's own start.
_NODE_NAME = 0x04
_NODE_ORIGIN = 0x08
_NODE_ROTATION = 0x10
_NODE_SCALE = 0x14
_NODE_ANCHOR = 0x1C
_NODE_SIZE = 0x44
_NODE_DATA = 0x4C
_LAYER_CHILDREN = 0x90
_REFERENCE_NAME = 0x70
_REFERENCE_ASSET = 0x74
_MASK_ASSET = 0x9C
_MASK_NAME = 0xA0

# Node data block. Offsets from the data block's start.
_DATA_COLOUR = 0x08
_DATA_OPACITY = 0x10
#: Where each kind of box keeps its texture references (offset + count).
_DATA_TEXTURES = {"Image": 0x40, "Ninegrid": 0x40, "Mask": 0x40,
                  "Counter": 0x40, "Ellipse": 0x50}
_TEXTURE_REF_SIZE = 0x2C
_DATA_NINEGRID_MARGINS = 0x68    # left, top, right, bottom
_DATA_TEXT_KEY = 0x40
_DATA_TEXT_FONT_SIZE = 0x48
_DATA_TEXT_SPACING = 0x50
_DATA_TEXT_LINE_HEIGHT = 0x54
_DATA_TEXT_VALIGN = 0x58
_DATA_TEXT_HALIGN = 0x5C

# Component record (0x40 bytes).
_COMPONENT_SIZE = 0x40
# Timeline record (0x60 bytes) and its elements (0x20 bytes).
_TIMELINE_SIZE = 0x60
_ELEMENT_SIZE = 0x20
_ELEMENT_VALUE = 0x74            # from the element's data block
_ELEMENT_EASING = 0x30
_ELEMENT_FRAME = 0x0C            # from the element's own record: its start
_ELEMENT_FRAMES = 0x10           # ...and its length, in frames
#: From the timeline inside a timeline record (at +8): its last frame.
#: Every key ends by it (all 56,877), and FF16Tools' writer refuses one that
#: doesn't. How long a frame lasts in the game isn't recorded in the file.
_TIMELINE_LAST_FRAME = 0x1C

#: Far deeper than any layout in the game (the deepest nests boxes 6 deep);
#: a file that goes past it is damaged - a group listing itself as its own
#: child - not deep.
_NEST_LIMIT = 64
#: Far more boxes than any layout in the game has (the most is 238). A file
#: past it is damaged: a group listing children other groups list too
#: multiplies the boxes with every level, and a few kilobytes of that is
#: billions of boxes - found by the independent review, not in any file.
_BOX_LIMIT = 10000


class UibError(ValueError):
    """Raised for a file this module cannot read as a UI layout."""


# =============================================================================
# The parts of a layout
# =============================================================================

@dataclass
class TextureRef:
    """A texture piece: the part list it comes from, and which part."""
    uri: str      # "UITextureParts://ui/ffto/bar/textureparts/ui_bar_parts_uitx"
    part: int     # index into that .utexpt's parts

    @property
    def part_list_path(self) -> str:
        """The .utexpt's path under the unpacked game folder."""
        return self.uri.split("://", 1)[-1] + ".utexpt"


@dataclass
class Box:
    """
    One node of a component's tree - a box on the screen.

    `offset` is where the node starts in the file; every number below was
    read from a fixed distance past it, which is what makes an in-place edit
    possible.
    """
    component: str
    path: str                 # "LayerRoot/Contents" - unique in its component
    kind: str
    offset: int
    origin: tuple
    rotation: float
    scale: tuple
    anchor: tuple
    size: tuple
    data_offset: Optional[int] = None
    colour: tuple = (255, 255, 255, 255)   # red, green, blue, alpha - file order
    opacity: float = 1.0
    textures: list = field(default_factory=list)    # list[TextureRef]
    margins: tuple = (0, 0, 0, 0)                   # Ninegrid only
    font_size: Optional[int] = None                 # Text only
    ui_key: int = 0
    h_align: int = 0
    v_align: int = 0
    line_height: int = 0
    spacing: int = 0
    reference_name: str = ""  # Reference only: the component it places
    reference_file: str = ""  # "" for this file, else "UI://ui/ffto/..."
    mask_name: str = ""       # Mask only: a component whose drawing is the mask
    mask_asset: str = ""      # Mask only: another file's asset, if any
    children: list = field(default_factory=list)    # list[Box], Layer only

    @property
    def key(self) -> str:
        """How an edit names this box: "Component/Path"."""
        return f"{self.component}/{self.path}"

    @property
    def name(self) -> str:
        return self.path.rsplit("/", 1)[-1]

    def editable_fields(self) -> tuple:
        fields = [FIELD_ORIGIN, FIELD_SIZE, FIELD_SCALE]
        if self.kind == "Text":
            fields.append(FIELD_FONT_SIZE)
        if self.data_offset is not None:
            # Every box in the game's 252 files has its data block, so every
            # box has a colour and an opacity; one without (a game update
            # could ship one) has nowhere to write them.
            fields += [FIELD_COLOUR, FIELD_OPACITY]
        return tuple(fields)

    def value(self, field_name: str):
        if field_name == FIELD_ORIGIN:
            return self.origin
        if field_name == FIELD_SIZE:
            return self.size
        if field_name == FIELD_SCALE:
            return self.scale
        if field_name == FIELD_FONT_SIZE:
            return self.font_size
        if field_name == FIELD_COLOUR:
            return self.colour
        if field_name == FIELD_OPACITY:
            return self.opacity
        raise KeyError(field_name)


@dataclass
class Key:
    """One animation step: a timeline setting something about one box."""
    component: str
    timeline: str
    kind: int                 # the element type, e.g. KEY_POSITION
    frame: int
    frames: int
    target: str               # the box's name, "" when not a box target
    data_offset: Optional[int]
    easing: int = 0
    values: tuple = ()
    index: int = 0            # its place in its animation
    offset: int = 0           # where its 0x20-byte record starts
    last_frame: int = 0       # its animation's last frame

    @property
    def value_offset(self) -> Optional[int]:
        return None if self.data_offset is None else self.data_offset + _ELEMENT_VALUE

    @property
    def id(self) -> str:
        """
        How an edit names this key: "Component/Animation/place". It survives
        a game update that leaves the animation's keys in their order; an
        edit is also checked against the key's kind and box when applied.
        No component or animation name in the game has a "/" in it, and no
        component has two animations of one name (checked on all 252).
        """
        return f"{self.component}/{self.timeline}/{self.index}"


@dataclass
class Component:
    name: str
    kind: str
    size: tuple
    offset: int
    blend: int = 0            # how it draws over what is behind; see BLEND_MODES
    boxes: list = field(default_factory=list)       # top-level boxes
    timelines: list = field(default_factory=list)   # timeline names, in order
    keys: list = field(default_factory=list)        # list[Key]


# =============================================================================
# Reading
# =============================================================================

class _Reader:
    def __init__(self, data: bytes):
        self.data = data

    def u32(self, at: int) -> int:
        return self._unpack("<I", at)

    def i32(self, at: int) -> int:
        return self._unpack("<i", at)

    def f32(self, at: int) -> float:
        return self._unpack("<f", at)

    def pair_i(self, at: int) -> tuple:
        return (self.i32(at), self.i32(at + 4))

    def pair_f(self, at: int) -> tuple:
        return (self.f32(at), self.f32(at + 4))

    def string_at(self, at: int) -> str:
        if at < 0 or at >= len(self.data):
            raise UibError(f"a name points outside the file (0x{at:X})")
        end = self.data.find(b"\0", at)
        if end < 0:
            raise UibError(f"a name at 0x{at:X} is not terminated")
        return self.data[at:end].decode("utf-8", errors="replace")

    def string_ptr(self, base: int, at: int) -> str:
        rel = self.i32(at)
        return "" if rel == 0 else self.string_at(base + rel)

    def _unpack(self, fmt: str, at: int):
        # A pointer before the start of the file is damage. Python would
        # read it from the END, and a writer would then write there.
        if at < 0:
            raise UibError(f"a pointer leads before the start of the file ({at})")
        try:
            return struct.unpack_from(fmt, self.data, at)[0]
        except struct.error:
            raise UibError(f"the file ends before offset 0x{at:X}") from None


class Layout:
    """
    A parsed `.uib`. Read-only; edits go through `apply_edits`, which works
    on the bytes and re-reads them.
    """

    def __init__(self, data: bytes):
        self.data = bytes(data)
        r = _Reader(self.data)
        if self.data[:4] != MAGIC:
            raise UibError("not a UI layout file (it does not start with UIB)")
        if r.u32(4) != VERSION:
            raise UibError(f"UI layout version {r.u32(4)}, only {VERSION} is known")
        self.components: dict = {}
        self.boxes: dict = {}
        toc = r.u32(0x18)
        comp_off, comp_count = r.i32(toc + 4), r.u32(toc + 8)
        if comp_count > 10000:
            raise UibError("implausible component count")
        for i in range(comp_count):
            self._read_component(r, toc + comp_off + i * _COMPONENT_SIZE)
        self._name_counts = {}
        for b in self.boxes.values():
            self._name_counts[(b.component, b.name)] = self._name_counts.get((b.component, b.name), 0) + 1
        #: Every animation step, by `Key.id`.
        self.keys = {k.id: k for c in self.components.values() for k in c.keys}

    # -- structure ----------------------------------------------------------

    def _read_component(self, r: _Reader, base: int) -> None:
        name = r.string_ptr(base, base)
        size = r.pair_i(base + 0x04)
        props = r.u32(base + 0x0C)
        kind = COMPONENT_KINDS.get(r.u32(base + props), f"Kind{r.u32(base + props)}")
        comp = Component(name=name, kind=kind, size=size, offset=base,
                         blend=r.u32(base + props + 0x10))
        if name in self.components:
            raise UibError(f"two components are called {name!r}")
        self.components[name] = comp
        nodes_off, node_count = r.u32(base + 0x10), r.u32(base + 0x14)
        for i in range(node_count):
            table = base + nodes_off
            comp.boxes.append(self._read_node(r, table + r.i32(table + i * 4), comp, "", 0))
        tl_off, tl_count = r.i32(base + 0x18), r.u32(base + 0x1C)
        for i in range(tl_count):
            self._read_timeline(r, base + tl_off + i * _TIMELINE_SIZE, comp)

    def _read_node(self, r: _Reader, base: int, comp: Component, parent: str,
                   depth: int) -> Box:
        if depth > _NEST_LIMIT:
            raise UibError(f"boxes in {comp.name} nest more than {_NEST_LIMIT} "
                           f"deep, so the file is damaged")
        kind_id = r.u32(base)
        name = r.string_ptr(base, base + _NODE_NAME)
        path = f"{parent}/{name}" if parent else name
        data_rel = r.i32(base + _NODE_DATA)
        box = Box(
            component=comp.name, path=path,
            kind=NODE_KINDS.get(kind_id, f"Kind{kind_id}"), offset=base,
            origin=r.pair_i(base + _NODE_ORIGIN),
            rotation=r.f32(base + _NODE_ROTATION),
            scale=r.pair_f(base + _NODE_SCALE),
            anchor=r.pair_i(base + _NODE_ANCHOR),
            size=r.pair_i(base + _NODE_SIZE),
            data_offset=base + data_rel if data_rel else None,
        )
        if box.key in self.boxes:
            raise UibError(f"two boxes are called {box.key!r}")
        if len(self.boxes) >= _BOX_LIMIT:
            raise UibError(f"more than {_BOX_LIMIT} boxes, so the file is damaged")
        self.boxes[box.key] = box
        d = box.data_offset
        if d is not None:
            r.u32(d + _DATA_COLOUR)                     # there, or UibError
            box.colour = tuple(self.data[d + _DATA_COLOUR:d + _DATA_COLOUR + 4])
            box.opacity = r.f32(d + _DATA_OPACITY)
            if box.kind in _DATA_TEXTURES:
                at = d + _DATA_TEXTURES[box.kind]
                t_off, t_count = r.i32(at), r.u32(at + 4)
                for i in range(min(t_count, 64)):
                    ref = d + t_off + i * _TEXTURE_REF_SIZE
                    asset = ref + r.i32(ref)
                    box.textures.append(TextureRef(
                        uri=r.string_ptr(asset, asset + 4), part=r.u32(ref + 8)))
            if box.kind == "Ninegrid":
                m = d + _DATA_NINEGRID_MARGINS
                box.margins = (r.i32(m), r.i32(m + 4), r.i32(m + 8), r.i32(m + 12))
            if box.kind == "Text":
                box.ui_key = r.i32(d + _DATA_TEXT_KEY)
                box.font_size = r.i32(d + _DATA_TEXT_FONT_SIZE)
                box.spacing = r.i32(d + _DATA_TEXT_SPACING)
                box.line_height = r.i32(d + _DATA_TEXT_LINE_HEIGHT)
                box.v_align = r.i32(d + _DATA_TEXT_VALIGN)
                box.h_align = r.i32(d + _DATA_TEXT_HALIGN)
        if box.kind == "Reference":
            box.reference_name = r.string_ptr(base, base + _REFERENCE_NAME)
            asset_rel = r.i32(base + _REFERENCE_ASSET)
            if asset_rel:
                asset = base + asset_rel
                box.reference_file = r.string_ptr(asset, asset + 4)
        if box.kind == "Mask":
            box.mask_name = r.string_ptr(base, base + _MASK_NAME)
            asset_rel = r.i32(base + _MASK_ASSET)
            if asset_rel:
                asset = base + asset_rel
                box.mask_asset = r.string_ptr(asset, asset + 4)
        if box.kind == "Layer":
            c_off, c_count = r.i32(base + _LAYER_CHILDREN), r.u32(base + _LAYER_CHILDREN + 4)
            table = base + c_off
            for i in range(c_count):
                box.children.append(self._read_node(r, table + r.i32(table + i * 4), comp, path,
                                                    depth + 1))
        return box

    def _read_timeline(self, r: _Reader, base: int, comp: Component) -> None:
        name = r.string_ptr(base, base)
        if name in comp.timelines:
            # A key names its animation by name: two of one name and an
            # edit could land on either's key.
            raise UibError(f"two animations in {comp.name} are called {name!r}")
        comp.timelines.append(name)
        tl = base + 8
        last_frame = r.u32(tl + _TIMELINE_LAST_FRAME)
        el_off, el_count = r.i32(tl + 4), r.u32(tl + 8)
        tg_off, tg_count = r.i32(tl + 0x14), r.i32(tl + 0x18)
        targets = []
        for i in range(max(0, tg_count)):
            table = tl + tg_off
            at = table + r.i32(table + i * 4)
            targets.append(r.string_ptr(at, at + 0x28)
                           if r.u32(at) == TARGET_COMPONENT_BOX else "")
        for i in range(el_count):
            e = tl + el_off + i * _ELEMENT_SIZE
            kind = r.u32(e + 0x08)
            target_index = r.u32(e + 0x14)
            data_rel = r.i32(e + 0x1C)
            data = e + data_rel if data_rel else None
            key = Key(component=comp.name, timeline=name, kind=kind,
                      frame=r.u32(e + _ELEMENT_FRAME), frames=r.u32(e + _ELEMENT_FRAMES),
                      target=targets[target_index] if target_index < len(targets) else "",
                      data_offset=data, index=i, offset=e, last_frame=last_frame)
            if data is not None:
                key.easing = r.i32(data + _ELEMENT_EASING)
                v = data + _ELEMENT_VALUE
                if kind in (KEY_POSITION, KEY_SIZE):
                    key.values = r.pair_i(v)
                elif kind == KEY_SCALE:
                    key.values = r.pair_f(v)
                elif kind == KEY_OPACITY:
                    key.values = (r.f32(v),)
                elif kind == KEY_COLOUR:
                    key.values = tuple(self.data[v:v + 4])
                elif kind == KEY_CHILD_TIMELINE:
                    key.values = (r.string_ptr(data, data + 0x30),)
            comp.keys.append(key)

    # -- questions ----------------------------------------------------------

    @property
    def root(self) -> Optional[Component]:
        """The component the game shows for this file: the Root one, else the last."""
        for comp in self.components.values():
            if comp.kind == "Root":
                return comp
        return list(self.components.values())[-1] if self.components else None

    def box(self, key: str) -> Optional[Box]:
        return self.boxes.get(key)

    def keys_for(self, box: Box, kind: int) -> list:
        """
        The keys of one kind that target `box`, from its own component.

        None when another box in the component has the same name, because a
        key names its box by name alone and could mean either.
        """
        if self.name_is_shared(box):
            return []
        comp = self.components[box.component]
        return [k for k in comp.keys if k.kind == kind and k.target == box.name]

    def name_is_shared(self, box: Box) -> bool:
        return self._name_counts.get((box.component, box.name), 0) > 1

    def moves_with(self, box: Box) -> int:
        """How many position keys a move of `box` also shifts."""
        return len(self.keys_for(box, KEY_POSITION))


def read_layout(path: Path) -> Layout:
    return Layout(Path(path).read_bytes())


# =============================================================================
# Texture part lists (.utexpt)
# =============================================================================

#: Where a layout's cutting lists live, and what they are called.
PART_LIST_EXTENSION = ".utexpt"
_PART_SIZE = 20                # a name offset, then x1, y1, x2, y2


@dataclass
class TexturePart:
    name: str
    rect: tuple               # x1, y1, x2, y2 in pixels on the sheet
    offset: int = 0           # where its 20 bytes start in the file


@dataclass
class PartList:
    texture_path: str         # "ui/ffto/bar/texture/ui_bar_parts_uitx.tex"
    parts: list               # list[TexturePart]; parts[0] is "TexturePart"


def read_part_list(data: bytes) -> PartList:
    """
    Parses a .utexpt.

    Part 0 is always named `TexturePart` and meant to be the whole sheet, but
    its rectangle is stale in some files (the tavern backgrounds say 1024x2048
    for a 2048x1024 sheet, and draw correctly), so callers treat part 0 as
    "the whole sheet" rather than trusting its numbers.
    """
    r = _Reader(bytes(data))
    texture_path = r.string_at(r.u32(0))
    table, count = r.u32(4), r.u32(8)
    parts = []
    names = {}
    for i in range(count):
        e = table + i * _PART_SIZE
        at = e + r.i32(e)
        # Each name read once: a damaged list pointing every part at one
        # long name would otherwise hold a copy of it per part.
        name = names.get(at)
        if name is None:
            name = names[at] = r.string_at(at)
        parts.append(TexturePart(name, (r.i32(e + 4), r.i32(e + 8), r.i32(e + 12), r.i32(e + 16)),
                                 e))
    return PartList(texture_path, parts)


# =============================================================================
# Editing, in place
# =============================================================================

class _Unwritable(Exception):
    """
    An edit that cannot be written as asked; the message says why, in words.
    Not a ValueError, so the conversions below cannot mistake one another's.
    """


def _is_whole(value) -> bool:
    """A whole number - an int, and not a bool (which Python counts as one)."""
    return isinstance(value, int) and not isinstance(value, bool)


def _is_number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _as_pair(value, kind=int) -> tuple:
    """
    Two numbers, as a list or tuple: whole ones for `int`, else through
    `kind` (`_f32`). Nothing is converted into a number: "12" is not (1, 2),
    and 100.9 is not 100 - the page only ever gives numbers, so anything
    else came from somewhere it shouldn't have, and is refused, not guessed.
    """
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise _Unwritable(f"{value!r} is not two numbers")
    a, b = value
    if kind is int:
        if not (_is_whole(a) and _is_whole(b)):
            raise _Unwritable(f"{value!r} is not two whole numbers")
        return (a, b)
    return (kind(a), kind(b))


def _f32(value, what: str = "a scale") -> float:
    """`value` as the file will hold it - a 32-bit float."""
    try:
        if not _is_number(value):
            raise ValueError
        value = float(value)
        if not math.isfinite(value):
            raise ValueError
        return struct.unpack("<f", struct.pack("<f", value))[0]
    except (TypeError, ValueError, OverflowError, struct.error):
        raise _Unwritable(f"{value!r} is not {what} the file can hold") from None


def _ratio(new, old):
    """new / old, or None on an axis the box rests at 0 on - nothing to scale by."""
    return new / old if old else None


def _as_colour(value) -> tuple:
    """Four whole numbers 0-255 - red, green, blue, alpha - or _Unwritable."""
    if isinstance(value, (list, tuple)) and len(value) == 4 \
            and all(_is_whole(c) and 0 <= c <= 255 for c in value):
        return tuple(value)
    raise _Unwritable(f"{value!r} is not a colour, which is four whole numbers "
                      f"from 0 to 255: red, green, blue and alpha")


def _as_opacity(value) -> float:
    opacity = _f32(value, "an opacity")
    if not 0.0 <= opacity <= 1.0:
        raise _Unwritable(f"{value!r} is outside 0 to 1, since opacity runs from 0 "
                          f"(not seen) to 1 (solid)")
    return opacity


def _writes_for(layout: "Layout", box: Box, field_name: str, value) -> list:
    """
    Every `(format, offset, values)` one field's edit writes: the box's own
    number and the animation keys that restate it. Nothing is written until
    all of them are known to fit, so an edit either lands whole or not at
    all.
    """
    if field_name == FIELD_ORIGIN:
        x, y = _as_pair(value)
        dx, dy = x - box.origin[0], y - box.origin[1]
        writes = [("<ii", box.offset + _NODE_ORIGIN, (x, y))]
        for k in layout.keys_for(box, KEY_POSITION):
            if len(k.values) != 2:
                continue                  # a key with no value to move
            kx, ky = k.values
            writes.append(("<ii", k.value_offset, (kx + dx, ky + dy)))
        return writes
    if field_name == FIELD_SIZE:
        w, h = _as_pair(value)
        rw, rh = _ratio(w, box.size[0]), _ratio(h, box.size[1])
        writes = [("<ii", box.offset + _NODE_SIZE, (w, h))]
        for k in layout.keys_for(box, KEY_SIZE):
            if len(k.values) != 2:
                continue
            kw, kh = k.values
            # k * new / old in exact integer arithmetic, rounded once: the
            # key that restates the resting size lands exactly on the new one.
            writes.append(("<ii", k.value_offset,
                           (round(kw * w / box.size[0]) if rw is not None else kw,
                            round(kh * h / box.size[1]) if rh is not None else kh)))
        return writes
    if field_name == FIELD_SCALE:
        # Rounded to what the file can hold BEFORE the ratio is taken, so
        # applying a scale read back out of an edited file reproduces that
        # file exactly - which is the test a mod's own copy has to pass to
        # be editable here.
        sx, sy = _as_pair(value, _f32)
        rx, ry = _ratio(sx, box.scale[0]), _ratio(sy, box.scale[1])
        writes = [("<ff", box.offset + _NODE_SCALE, (sx, sy))]
        for k in layout.keys_for(box, KEY_SCALE):
            if len(k.values) != 2:
                continue
            kx, ky = k.values
            writes.append(("<ff", k.value_offset,
                           (kx * rx if rx is not None else kx,
                            ky * ry if ry is not None else ky)))
        return writes
    if field_name == FIELD_FONT_SIZE:
        if box.data_offset is None:
            raise _Unwritable("this text box has no text settings in the file")
        if not _is_whole(value):
            raise _Unwritable(f"{value!r} is not a text size")
        return [("<i", box.data_offset + _DATA_TEXT_FONT_SIZE, (value,))]
    if field_name in (FIELD_COLOUR, FIELD_OPACITY) and box.data_offset is None:
        raise _Unwritable(f"this box has no {field_name} in the file")
    if field_name == FIELD_COLOUR:
        rgba = _as_colour(value)
        writes = [("<4B", box.data_offset + _DATA_COLOUR, rgba)]
        for k in layout.keys_for(box, KEY_COLOUR):
            # Only the keys restating the resting colour follow it. The others
            # are another state's colour - a highlight under the cursor, the
            # red of a cost that can't be paid - and stay what they were.
            if tuple(k.values) == box.colour:
                writes.append(("<4B", k.value_offset, rgba))
        return writes
    if field_name == FIELD_OPACITY:
        # Rounded to what the file holds before the ratio is taken, as scale
        # is, so re-applying the value read back out of an edited file
        # reproduces that file exactly.
        new = _as_opacity(value)
        old = box.opacity
        writes = [("<f", box.data_offset + _DATA_OPACITY, (new,))]
        if not (math.isfinite(old) and old > 0):
            # Resting at 0 - hidden until an animation shows it - there is
            # no ratio to scale by, and the keys are left as they are. (16
            # boxes rest at 0.00001 instead, their keys switching between
            # that and 1: they scale like any other, the 1s staying at 1.)
            return writes
        for k in layout.keys_for(box, KEY_OPACITY):
            if k.value_offset is None or len(k.values) != 1:
                continue
            (at,) = k.values
            if not 0.0 <= at <= 1.0:
                continue                  # none in the game; left alone if seen
            # Each keeps its proportion of the resting value, never above 1.
            # The key restating it lands exactly on the new value: `new` is
            # a 32-bit float, and old * new / old in doubles is within a
            # rounding of it (checked on every resting opacity in the game
            # against 6,001 new values: 336,056 pairs, none off).
            writes.append(("<f", k.value_offset, (min(1.0, at * new / old),)))
        return writes
    raise _Unwritable(f"{field_name} is not something this tool edits")


def _key_writes(key: Key, edit: dict) -> list:
    """
    Every `(format, offset, values)` one animation key's edit writes: its
    start frame and length in its record, its easing and value in its data
    block. Checked first against the key the edit was made on - the same
    kind, setting the same box, starting at the same frame (`was_frame`) -
    so an animation a game update reordered is a reported problem, not a
    value written onto the wrong key. A neighbour taking a key's place has
    another start frame: keys of one box and kind play in order, 6,533
    tracks of several keys in the game and every one in strictly rising
    frames.
    """
    try:
        kind, target, was = edit["kind"], edit["target"], edit["was_frame"]
    except (TypeError, KeyError):
        raise _Unwritable("the edit doesn't say which key it was made on") from None
    if not (_is_whole(kind) and isinstance(target, str) and _is_whole(was)):
        raise _Unwritable("the edit doesn't say which key it was made on")
    if (kind, target, was) != (key.kind, key.target, key.frame):
        raise _Unwritable(f"in this version of the file that key is kind {key.kind} of "
                          f"{key.target or 'no box'} at frame {key.frame}, not kind {kind} "
                          f"of {target} at frame {was}")
    if key.kind not in EDITABLE_KEY_KINDS or key.data_offset is None:
        raise _Unwritable(f"a key of kind {key.kind} isn't read here, so it isn't edited")
    writes = []
    for name, at in (("frame", key.offset + _ELEMENT_FRAME),
                     ("frames", key.offset + _ELEMENT_FRAMES)):
        if name in edit:
            if not _is_whole(edit[name]) or edit[name] < 0:
                raise _Unwritable(f"{edit[name]!r} is not a {'start frame' if name == 'frame' else 'length'}"
                                  f", which is a whole number, 0 or more")
            writes.append(("<I", at, (edit[name],)))
    # Within its animation, as every key in the game is (FF16Tools' own
    # writer refuses one that isn't).
    end = edit.get("frame", key.frame) + edit.get("frames", key.frames)
    if end > key.last_frame:
        raise _Unwritable(f"it would end at frame {end}, after its animation's last "
                          f"frame, {key.last_frame}")
    if key.kind in KEY_VALUE_FORMATS:
        if "easing" in edit:
            if not _is_whole(edit["easing"]):
                raise _Unwritable(f"{edit['easing']!r} is not an easing kind, which is a "
                                  f"whole number")
            writes.append(("<i", key.data_offset + _ELEMENT_EASING, (edit["easing"],)))
        if "value" in edit:
            value = edit["value"]
            if key.kind in (KEY_POSITION, KEY_SIZE):
                value = _as_pair(value)
            elif key.kind == KEY_SCALE:
                value = _as_pair(value, _f32)
            elif key.kind == KEY_COLOUR:
                value = _as_colour(value)
            else:
                try:
                    (single,) = value
                except (TypeError, ValueError):
                    raise _Unwritable(f"{value!r} is not one opacity") from None
                value = (_as_opacity(single),)
            writes.append((KEY_VALUE_FORMATS[key.kind], key.value_offset, value))
    return writes


def apply_edits(data: bytes, edits: dict) -> tuple:
    """
    Returns `(patched bytes, problems)`.

    `edits` is `{"Component/Path": {field: value}}` with values meant as the
    box's new resting value: `origin` and `size` as two ints, `scale` as two
    floats, `font_size` as an int, `colour` as four ints 0-255 (red, green,
    blue, alpha), `opacity` as a float 0-1. Deltas and ratios are taken from
    the file being patched - the game's own copy at export time - so an edit
    stays right when a game update moves the box it started from.

    Animation keys edited directly are under `ANIMATION_KEYS`: `{key id:
    {"kind", "target", "was_frame", "frame", "frames", "easing", "value"}}`,
    `kind`, `target` and `was_frame` (its start frame in the game's copy)
    saying which key it was made on, the rest what it becomes (a value as a
    list: two numbers, four for a colour, one for an opacity). They are
    written after the boxes, so **a key edited directly keeps the value it
    was given** even when its box is moved, resized, recoloured or faded too
    - the edit is the key's final value. A key must stay inside its
    animation, and in order among the keys of its box and kind; an edit that
    would put any of them out of order is refused with the others of that
    box and kind edited alongside it. A key edit that changes nothing leaves
    nothing in the file, so a mod opened again doesn't have it.

    Every change overwrites bytes that already exist; the result is always
    the same length as the input. `problems` lists edits that could not be
    applied (a box a game update removed, a field a box does not have, a
    number the file cannot hold, a key that is not the one it was made on)
    in words, and those edits are skipped whole rather than guessed at or
    half written - with one exception: a box whose name another box in its
    component shares gets its own new value, and the problem says its keys
    were left as they are, because a key names its box by name alone.
    """
    layout = Layout(data)
    out = bytearray(layout.data)
    problems = []
    if not isinstance(edits, dict):
        return bytes(out), ["not written, as the edits are not a list of boxes"]
    for key, fields in edits.items():
        if key == ANIMATION_KEYS:
            continue
        box = layout.boxes.get(key)
        if box is None:
            problems.append(f"{key}: no such box in this version of the file")
            continue
        if not isinstance(fields, dict):
            problems.append(f"{key}: not written, as the edit is not a list of numbers")
            continue
        for field_name, value in fields.items():
            if field_name not in box.editable_fields():
                problems.append(f"{key}: a {box.kind} box has no {field_name}")
                continue
            if field_name in KEYED_FIELDS and layout.name_is_shared(box):
                # Keys name their box by name alone. No file shares a name
                # inside a component (checked on all 252), but if one ever
                # did, its keys could belong to either box.
                problems.append(f"{key}: another box in {box.component} has "
                                f"the same name, so its animation keys were "
                                f"not changed")
            try:
                writes = _writes_for(layout, box, field_name, value)
                for fmt, _at, values in writes:
                    struct.pack(fmt, *values)
            except _Unwritable as exc:
                problems.append(f"{key}: {field_name} not written, as {exc}")
                continue
            except (struct.error, OverflowError):
                problems.append(f"{key}: {field_name} not written, as a number "
                                f"is outside what the file can hold")
                continue
            for fmt, at, values in writes:
                struct.pack_into(fmt, out, at, *values)
    key_edits = edits.get(ANIMATION_KEYS) or {}
    if not isinstance(key_edits, dict):
        problems.append("animation keys: not written, as the edit is not a list of keys")
        key_edits = {}
    planned = {}
    for key_id, edit in key_edits.items():
        key = layout.keys.get(key_id)
        if key is None:
            problems.append(f"animation key {key_id}: no such key in this version of the file")
            continue
        try:
            writes = _key_writes(key, edit)
            for fmt, _at, values in writes:
                struct.pack(fmt, *values)
        except _Unwritable as exc:
            problems.append(f"animation key {key_id}: not written, as {exc}")
            continue
        except (struct.error, OverflowError):
            problems.append(f"animation key {key_id}: not written, as a number is outside "
                            f"what the file can hold")
            continue
        planned[key_id] = (writes, edit.get("frame", key.frame))
    for key_id in _out_of_order(layout, planned):
        key = layout.keys[key_id]
        problems.append(f"animation key {key_id}: not written, as it would put the "
                        f"{key.timeline} keys of {key.target or 'no box'} of its kind out of "
                        f"order, and they play in order")
        del planned[key_id]
    for writes, _frame in planned.values():
        for fmt, at, values in writes:
            struct.pack_into(fmt, out, at, *values)
    return bytes(out), problems


def _out_of_order(layout: "Layout", planned: dict) -> list:
    """
    The key edits in `planned` (`{key id: (writes, new start frame)}`) that
    leave one box's keys of one kind, in one animation, out of order - every
    edited key of such a track, as none of them can be said to be the one.
    """
    tracks = {}
    for key in layout.keys.values():
        tracks.setdefault((key.component, key.timeline, key.kind, key.target), []).append(key)
    refused = []
    for members in tracks.values():
        edited = [k for k in members if k.id in planned]
        if not edited or len(members) < 2:
            continue
        frames = [planned[k.id][1] if k.id in planned else k.frame
                  for k in sorted(members, key=lambda k: k.index)]
        if any(later <= earlier for earlier, later in zip(frames, frames[1:])):
            refused += [k.id for k in edited]
    return refused


def key_edit_for(key: Key) -> dict:
    """
    A key as an edit would set it: everything a key edit holds, at `key`'s
    values - a key of the game's own copy, whose start frame is the one the
    edit is checked against (`was_frame`).
    """
    edit = {"kind": key.kind, "target": key.target, "was_frame": key.frame,
            "frame": key.frame, "frames": key.frames}
    if key.kind in KEY_VALUE_FORMATS:
        edit["easing"] = key.easing
        edit["value"] = list(key.values)
    return edit


def edits_between(game: bytes, other: bytes) -> Optional[dict]:
    """
    The edits that turn the game's file into `other`, or None when no set of
    edits does.

    Used when a mod is opened: a layout the mod ships becomes editable here
    only when re-applying the recovered edits to the game's file reproduces
    the mod's copy byte for byte. Anything else - a file edited with another
    tool, or carrying changes this module does not model - is left to be
    carried through untouched, which is what always happened before this
    page existed. It cannot tell a modder's change from a game update's: a
    copy made against another game version, differing from this one only
    in numbers the page edits, comes back as edits of those numbers.

    Never raises: `other` is whatever a mod folder held, and a damaged file
    is one more file to carry through as it is, not a reason for opening
    the mod to stop half-way.
    """
    try:
        return _edits_between(game, other)
    except Exception:                                          # noqa: BLE001
        return None


def _as_held(value):
    """
    A field's value with its floats as the four bytes the file holds, so two
    copies are compared as the file compares them: a NaN equals itself, and
    -0.0 is not 0.0.
    """
    if isinstance(value, float):
        return struct.pack("<f", value)
    if isinstance(value, tuple):
        return tuple(_as_held(v) for v in value)
    return value


def _edits_between(game: bytes, other: bytes) -> Optional[dict]:
    try:
        g, o = Layout(game), Layout(other)
    except UibError:
        return None
    if g.boxes.keys() != o.boxes.keys():
        return None
    edits = {}
    for key, gb in g.boxes.items():
        ob = o.boxes[key]
        if gb.offset != ob.offset or gb.kind != ob.kind:
            return None
        changed = {}
        for field_name in gb.editable_fields():
            if _as_held(gb.value(field_name)) != _as_held(ob.value(field_name)):
                value = ob.value(field_name)
                changed[field_name] = list(value) if isinstance(value, tuple) else value
        if changed:
            edits[key] = changed
    # The boxes first, then what is left: the keys the boxes' edits don't
    # account for, each as an edit of its own (`apply_edits` writes them
    # last, so they are their final values).
    moved, problems = apply_edits(game, edits)
    if problems:
        return None
    m = Layout(moved)
    if m.keys.keys() != o.keys.keys():
        return None
    key_edits = {}
    for key_id, mk in m.keys.items():
        ok = o.keys[key_id]
        if (mk.kind, mk.target, mk.offset, mk.data_offset) != (ok.kind, ok.target, ok.offset,
                                                               ok.data_offset):
            return None
        same = (mk.frame, mk.frames) == (ok.frame, ok.frames)
        valued = mk.kind in KEY_VALUE_FORMATS and mk.value_offset is not None
        if valued:
            span = struct.calcsize(KEY_VALUE_FORMATS[mk.kind])
            same = same and mk.easing == ok.easing \
                and m.data[mk.value_offset:mk.value_offset + span] \
                == o.data[ok.value_offset:ok.value_offset + span]
        if not same:
            # Only what differs, beside which key it is: a number the edit
            # doesn't change is left to follow its box, as it did.
            edit = {"kind": ok.kind, "target": ok.target, "was_frame": mk.frame}
            if ok.frame != mk.frame:
                edit["frame"] = ok.frame
            if ok.frames != mk.frames:
                edit["frames"] = ok.frames
            if valued:
                if ok.easing != mk.easing:
                    edit["easing"] = ok.easing
                if m.data[mk.value_offset:mk.value_offset + span] \
                        != o.data[ok.value_offset:ok.value_offset + span]:
                    edit["value"] = list(ok.values)
            key_edits[key_id] = edit
    if key_edits:
        edits[ANIMATION_KEYS] = key_edits
    patched, problems = apply_edits(game, edits)
    if problems or patched != o.data:
        return None
    return edits


# =============================================================================
# Editing a part list, in place
# =============================================================================
#
# A part's corners are overwritten where they sit, as a layout's numbers are:
# nothing is added, removed or moved, so the file keeps its length and every
# byte of it but the sixteen changed. An edit names its part by its place in
# the list - the number the layouts use to name it - AND by its name, which
# is checked when the edit is applied: a game update that renumbered a list
# gets a reported problem, never a rectangle written onto another picture.
#
# Part 0 is not edited. It is meant to be the whole sheet; its numbers are
# out of date in 4 of the tavern's 9 lists (3 say 1024 x 2048 for a 2048 x
# 1024 sheet), the game shows those pictures whole regardless, and what it
# would do with a changed part 0 is not known.

def _as_rect(value) -> tuple:
    if isinstance(value, (list, tuple)) and len(value) == 4 \
            and all(_is_whole(c) for c in value):
        x1, y1, x2, y2 = value
        try:
            struct.pack("<4i", *value)
        except struct.error:
            raise _Unwritable(f"{value!r} is outside what the file can hold") from None
        # Every part in the tavern's lists but part 0 is like this; a part
        # turned inside out or off the sheet's top-left is not a part.
        if 0 <= x1 < x2 and 0 <= y1 < y2:
            return tuple(value)
        raise _Unwritable(f"{value!r} is not a part, since its top left corner must be above and "
                          f"left of its bottom right one, and neither below 0")
    raise _Unwritable(f"{value!r} is not a part's corners, which are four whole "
                      f"numbers: x1, y1, x2, y2")


def apply_part_edits(data: bytes, edits: dict) -> tuple:
    """
    Returns `(patched bytes, problems)` for a part list (`.utexpt`).

    `edits` is `{index: {"name": str, "rect": [x1, y1, x2, y2]}}`: the part
    at that place in the list, which must still be called `name`, gets those
    corners. An edit that cannot be applied - no such part in this version
    of the list, a part called something else there now, part 0, corners
    that are not four whole numbers - is skipped whole and said in
    `problems`.
    """
    parts = read_part_list(data)
    out = bytearray(data)
    problems = []
    if not isinstance(edits, dict):
        return bytes(out), ["not written, as the edits are not a list of parts"]
    for index, edit in edits.items():
        if not _is_whole(index):
            problems.append(f"part {index!r}: not written, as a part is named by its "
                            f"place in the list, a whole number")
            continue
        i = index
        try:
            name = edit["name"]
            rect = _as_rect(edit["rect"])
        except (TypeError, KeyError):
            problems.append(f"part {index}: not written, as the edit is not a part's name "
                            f"and corners")
            continue
        except _Unwritable as exc:
            problems.append(f"part {index} ({edit.get('name', '?')}): not written, as {exc}")
            continue
        if i == 0:
            problems.append("part 0: not written, as it is the whole sheet and the game doesn't "
                            "use its numbers as they are")
            continue
        if not 0 < i < len(parts.parts):
            problems.append(f"part {i} ({name}): no such part in this version of the list")
            continue
        if parts.parts[i].name != name:
            problems.append(f"part {i}: not written, as it is called {parts.parts[i].name!r} in "
                            f"this version of the list, not {name!r}")
            continue
        struct.pack_into("<4i", out, parts.parts[i].offset + 4, *rect)
    return bytes(out), problems


def part_edits_between(game: bytes, other: bytes) -> Optional[dict]:
    """
    The part edits that turn the game's part list into `other`, or None
    when none do - the same test `edits_between` puts a layout to: taken
    over only if re-applying the edits reproduces `other` byte for byte.
    Never raises.
    """
    try:
        # Anything but corners differing - a name, the sheet it names, its
        # length, part 0 - fails the byte-for-byte test below, so it needs
        # no test of its own.
        g, o = read_part_list(game), read_part_list(other)
        edits = {i: {"name": gp.name, "rect": list(op.rect)}
                 for i, (gp, op) in enumerate(zip(g.parts, o.parts)) if gp.rect != op.rect}
        patched, problems = apply_part_edits(game, edits)
        if problems or patched != bytes(other):
            return None
        return edits
    except Exception:                                          # noqa: BLE001
        return None


# =============================================================================
# Browsing
# =============================================================================

@dataclass
class LayoutTreeNode:
    """One folder or file in the tree of layouts, shaped like the texture tree."""
    name: str
    relative_path: str        # forward-slashed from the unpacked game folder
    is_file: bool
    children: list = field(default_factory=list)


def scan_layout_tree(unpacked_game_dir: Path) -> LayoutTreeNode:
    """
    Every .uib under <unpacked game>/ui, pruned of folders with none.

    All 252 of the game's layouts live under ui/ (checked against the
    project's listing of the unpacked game), so the scan starts there
    rather than walking the whole game.
    """
    root = Path(unpacked_game_dir) / LAYOUT_ROOT

    def scan_dir(path: Path, rel: str) -> Optional[LayoutTreeNode]:
        children = []
        try:
            entries = sorted(path.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
        except OSError:
            return None
        for entry in entries:
            entry_rel = f"{rel}/{entry.name}"
            if entry.is_dir():
                sub = scan_dir(entry, entry_rel)
                if sub is not None:
                    children.append(sub)
            elif entry.is_file() and entry.suffix.lower() == LAYOUT_EXTENSION:
                children.append(LayoutTreeNode(entry.name, entry_rel, True))
        if not children:
            return None
        return LayoutTreeNode(path.name, rel, False, children)

    found = scan_dir(root, LAYOUT_ROOT) if root.is_dir() else None
    return found or LayoutTreeNode(LAYOUT_ROOT, LAYOUT_ROOT, False)


def count_layouts(node: LayoutTreeNode) -> int:
    if node.is_file:
        return 1
    return sum(count_layouts(child) for child in node.children)


def layout_paths(node: LayoutTreeNode):
    """Every layout's path in the tree, spelled as the game spells it."""
    if node.is_file:
        yield node.relative_path
    for child in node.children:
        yield from layout_paths(child)


def layout_path_for(reference_file: str) -> str:
    """"UI://ui/ffto/common/ffto_common_window" -> "ui/ffto/common/ffto_common_window.uib"."""
    return reference_file.split("://", 1)[-1] + LAYOUT_EXTENSION
