"""
Which textures a box on a UI layout draws - for the UI Layouts page's
right-click jump to the Textures page.

A box names its pictures through its part lists: each texture reference
names a `.utexpt`, and the part list names the texture sheet
(`PartList.texture_path`). A group or a piece draws whatever the boxes in
it draw, including pieces placed from other layout files, wherever those
live.

Two cases jump to a FOLDER rather than to one file, and the menu says why:

- **A group or piece drawing from several textures** - their folder, when
  they share one.
- **A picture the game swaps for another while it runs.** Measured on the
  tavern: its layout names `ui_bar_bg_00_uitx.tex`, but the game shows
  `bg_00`, `bg_01` or `bg_02` by chapter (research notes, "Ramza moved, and
  also stayed"). The file cannot say which pictures are swapped like that,
  so the page offers the folder whenever a texture has siblings named like
  it but for their number - the file first, the folder beside it, and the
  menu says the game MAY show one of those instead.

Nothing here imports widgets; the page builds the menu.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from .. import uib

#: Deeper than any layout nests pieces (the game's deepest is 6).
_DEPTH_LIMIT = 16

#: Why a box has no texture to open, by its kind - read after "No texture to
#: open as" in the right-click menu, so each is the rest of that sentence.
NO_PICTURE = {
    "Text": "a text box draws its words, not a picture",
    "Rect": "a colour box is filled with a colour, not a picture",
    "Collision": "a click area is never drawn",
    "Bezier": "a line is drawn, not a picture",
    "Ellipse": "an ellipse is drawn, not a picture",
    "Mask": "it is cut from another piece's shape, not from a picture",
    "Image": "the game sets its picture while it runs",
    "Ninegrid": "the game sets its picture while it runs",
    "Layer": "nothing in this group draws a picture",
    "Reference": "nothing in this piece draws a picture",
    "Counter": "the game sets its picture while it runs",
}


@dataclass
class TextureTargets:
    """What a box's pictures come from."""
    sheets: list = field(default_factory=list)   # texture paths in the game, sorted
    absent: list = field(default_factory=list)   # part lists or textures named but not there
    nothing: str = ""                            # why there is no picture at all


def folder_of(path: str) -> str:
    return path.rsplit("/", 1)[0] if "/" in path else ""


def targets_for(game_dir: Path, layout: uib.Layout, key: Optional[str] = None,
                component: Optional[str] = None,
                load: Optional[Callable] = None) -> TextureTargets:
    """
    The textures box `key` draws - or, with `component`, a whole piece of
    this file (the screen itself is its root piece).

    `load(rel) -> uib.Layout | None` reads another layout file, for pieces
    placed from one; by default the game's own copy.
    """
    game_dir = Path(game_dir)
    cache = {}

    def default_load(rel):
        if rel not in cache:
            try:
                cache[rel] = uib.Layout((game_dir / rel).read_bytes())
            except (OSError, uib.UibError):
                cache[rel] = None
        return cache[rel]

    load = load or default_load
    refs, reasons, absent = [], [], []
    seen = set()

    def walk(lay, boxes, rel, depth):
        for box in boxes:
            refs.extend(t for t in box.textures if t.uri)
            walk(lay, box.children, rel, depth)
            if box.kind != "Reference" or depth >= _DEPTH_LIMIT:
                continue
            if not box.reference_name:
                reasons.append("the game fills this slot in while it runs")
                continue
            other_rel, other = rel, lay
            if box.reference_file:
                other_rel = uib.layout_path_for(box.reference_file)
                other = load(other_rel)
                if other is None:
                    absent.append(other_rel)
                    reasons.append("the file its piece comes from isn't in your unpacked game")
                    continue
            piece = other.components.get(box.reference_name)
            if piece is None:
                reasons.append("the piece it places isn't in its file")
                continue
            if (other_rel, piece.name) in seen:
                continue
            seen.add((other_rel, piece.name))
            walk(other, piece.boxes, other_rel, depth + 1)

    if component is not None:
        piece = layout.components.get(component)
        if piece is not None:
            walk(layout, piece.boxes, "", 0)
        kind = "Reference"
    else:
        box = layout.boxes.get(key or "")
        if box is None:
            return TextureTargets(nothing="there is no such box")
        walk(layout, [box], "", 0)
        kind = box.kind

    sheets = set()
    lists = {}
    for ref in refs:
        rel = ref.part_list_path
        if rel not in lists:
            try:
                lists[rel] = uib.read_part_list((game_dir / rel).read_bytes()).texture_path
            except (OSError, uib.UibError):
                lists[rel] = None
                absent.append(rel)
        texture = lists[rel]
        if texture is None:
            continue
        if (game_dir / texture).is_file():
            sheets.add(texture)
        elif texture not in absent:
            absent.append(texture)
    nothing = ""
    if not sheets:
        if absent:
            nothing = "its picture isn't in your unpacked game"
        elif reasons and kind == "Reference" and len(set(reasons)) == 1:
            nothing = reasons[0]
        else:
            nothing = NO_PICTURE.get(kind, "it draws no picture")
    return TextureTargets(sorted(sheets), sorted(set(absent)), nothing)


def swapped_siblings(game_dir: Path, texture: str) -> list:
    """
    Textures in the same folder named like `texture` but for their numbers:
    `ui_bar_bg_00_uitx.tex` -> `ui_bar_bg_01_uitx.tex`, `ui_bar_bg_02_uitx.tex`.
    A name with no number in it has none.
    """
    name = texture.rsplit("/", 1)[-1]
    pieces = re.split(r"\d+", name)
    if len(pieces) < 2:
        return []
    pattern = re.compile(r"\d+".join(re.escape(p) for p in pieces) + r"\Z", re.IGNORECASE)
    folder = Path(game_dir) / folder_of(texture)
    try:
        names = sorted(p.name for p in folder.iterdir() if p.is_file())
    except OSError:
        return []
    return [n for n in names if n != name and pattern.match(n)]


#: How a layout names a part list: `UITextureParts://ui/ffto/.../name_uitx`.
_PART_LIST_NAME = re.compile(rb"UITextureParts://([^\x00]+)\x00")


def part_list_users(game_dir: Path) -> dict:
    """
    `{part list path: [layout paths naming it]}` across the unpacked game's
    layouts - for the page to say how many screens a part list's change
    reaches before anyone makes it. 95 of the 297 lists the game's layouts
    use are shared, one by 52 screens.

    Read off the bytes, every `UITextureParts://...` a layout holds, rather
    than through the reader: on all 252 files that finds every list the
    reader's picture boxes name, and 3 more named elsewhere (a talk window's
    mask, a face mask, a world-map blur). A count given as a warning should
    not come up short. It takes about 20 ms.
    """
    game_dir = Path(game_dir)
    users = {}
    try:
        layouts = uib.layout_paths(uib.scan_layout_tree(game_dir))
    except OSError:
        return {}
    for rel in layouts:
        try:
            data = (game_dir / rel).read_bytes()
        except OSError:
            continue
        for match in _PART_LIST_NAME.finditer(data):
            name = match.group(1).decode("utf-8", errors="replace") + uib.PART_LIST_EXTENSION
            users.setdefault(name, set()).add(rel)
    return {name: sorted(files) for name, files in users.items()}
