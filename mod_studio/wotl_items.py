"""
(16 November 2026; Mod Studio Framework 2.0.0 in the making) War of the
Lions' 40 items, as Mod Studio Framework gives them.

Zodi's first point of 16 November: "Like we made Dark Knight and Onion Onion
In Mod Studio Framework we should do the same for WotLs items from WotL
Restoration to be able to be used by the framework so they can be edited on
the Items page and can be used in Encounters page and modders new Battles and
for Treasure Hunter."

**Nothing of the 40 is in the game** (`claude/wotl-items-research.md`): the
framework carries each whole (`helper/ModStudioEventSetup/WotLItems.cs`), at
WotL Restoration's numbers (261 to 313, with gaps), with War of the Lions'
own stats (FFTPatcher's PSP files, Glain's, GPL-3, read for facts), Zodi's
own icons and War of the Lions' descriptions as he gave them. This module is
Mod Studio's copy of the same table (`data/WotLItems.json`, written by
`dev/research/sidequests/wotl_items.py --json` from the same measure that
writes the framework's, and held to it by `dev/test_mod_battles.py`).

**A mod asks for them** with `ModStudioWotLItems.json` at its root, read here
as the framework reads it (`WotLItems.Read`):

    { "Format": "Mod Studio War of the Lions items", "Version": 1,
      "Items": [ { "Item": 262, ...an item as an item.json gives one... } ] }

The file's being there is the asking: Mod Studio writes it whenever the mod
names one of the 40 anywhere (a unit, a treasure, a quest's unit or reward)
or changes one on the Items page. `Items` holds the mod's own version of each
item it changed, a whole item in `item.json`'s format (`mod_items.ModItem`)
with `"Item"`, its number; none when it changed none.

Nothing here imports Qt.
"""
from __future__ import annotations

import copy
import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Optional

from . import helper_json as hj
from . import mod_items as mi
from . import paths

#: Mod Studio's copy of the table, among its bundled data.
TABLE_FILE = "WotLItems.json"
TABLE_FORMAT = "Mod Studio War of the Lions items table"
#: The file at a mod's root that asks the framework for them (the helper's `WotLItems`).
FILE = "ModStudioWotLItems.json"
FORMAT = "Mod Studio War of the Lions items"
VERSION = 1
#: WotL Restoration's numbers for them (its first and its last: 55 numbers, 40 of which hold an item).
FIRST, LAST = 261, 315
#: Whose they are, in words.
OWNER = "War of the Lions"


def icon_name(number: int) -> str:
    """The name of an item's own icon's files, which the framework carries beside itself at the game's paths
    (`WotLItems.IconName`): a mod's own version of the item keeps that icon by naming it."""
    return f"msf_wotl_{int(number)}"


@dataclass(frozen=True)
class Fact:
    """One of the 40 as the framework carries it: its number, War of the Lions' name, its kind (`mod_items.KINDS`),
    its records (since the thirty third session the record's first two bytes and a weapon's or shield's sprite pair
    its looks in battle matched to Zodi's icon, `dev/research/sidequests/wotl_looks.py`), the game's nearest item
    (`near`: whose icon stands for it where an item must name one; its look in battle until then), its Item row's UI
    category and sort, and its description as Zodi gave it."""
    number: int
    name: str
    kind: int
    record: bytes
    kind_record: bytes
    bonus: Optional[bytes]
    near: int
    pair: bytes
    ui_category: int
    sort: int
    description: str


def _fact(entry: dict) -> Fact:
    bonus = entry.get("Bonus")
    return Fact(int(entry["Item"]), str(entry["Name"]), mi.KINDS.index(entry["Kind"]),
                bytes.fromhex(entry["Record"]), bytes.fromhex(entry["KindRecord"]),
                bytes.fromhex(bonus) if bonus else None, int(entry["Icon"]), bytes.fromhex(entry["Pair"]),
                int(entry["UiCategory"]), int(entry["Sort"]), str(entry["Description"]))


@lru_cache(maxsize=None)
def _table(path: str) -> tuple:
    top = json.loads(Path(path).read_text(encoding="utf-8"))
    if top.get("Format") != TABLE_FORMAT:
        raise ValueError(f"{Path(path).name} isn't Mod Studio's table of War of the Lions' items")
    return tuple(_fact(entry) for entry in top["Items"])


def facts(path=None) -> tuple:
    """The 40, in their numbers' order. An empty tuple when the table can't be read (a build without it): the
    pages then offer none of them."""
    try:
        return _table(str(path or (paths.bundled_data_dir() / TABLE_FILE)))
    except (OSError, ValueError, KeyError, TypeError):
        return ()


def fact(number) -> Optional[Fact]:
    """One of the 40 by its number, None for a number that holds none."""
    return next((f for f in facts() if f.number == number), None)


def numbers() -> tuple:
    return tuple(f.number for f in facts())


def names() -> dict:
    """`{number: War of the Lions' name}` for the 40."""
    return {f.number: f.name for f in facts()}


def is_one(ref) -> bool:
    """Whether `ref` is one of the 40 by its number."""
    return isinstance(ref, int) and not isinstance(ref, bool) and fact(ref) is not None


def ui_values(item: Fact) -> tuple:
    """The Item row's UI status effect and random damage for what a weapon does (`WotLItems.Shown`)."""
    if item.kind != mi.WEAPON:
        return 0, False
    formula, kind = item.kind_record[2], item.record[5]
    return (1001 if formula == 6 else 1002 if formula == 7 else 0), kind in (6, 9, 0x11) or formula == 4


def item_of(found: Fact) -> mi.ModItem:
    """One of the 40 as the framework gives it with nothing of a mod's (`WotLItems.Item`): its name its words'
    name, singular and plural, its description, its own icon (as an item's file names an icon of its own: no
    game item's number beside it, so the item written and read back is the same item)."""
    ui_status, random_damage = ui_values(found)
    return mi.ModItem(found.name, found.kind, bytes(found.record), bytes(found.kind_record), bytes(found.pair),
                      bytes(found.bonus) if found.bonus is not None else None, found.name, found.name, found.name,
                      found.description, 0, icon_name(found.number), found.ui_category, found.sort, (),
                      ui_status, random_damage)


def item(number, changed: Optional[dict] = None) -> Optional[mi.ModItem]:
    """One of the 40 as the mod has it: its own version where it changed it (`changed`: `state.wotl_items`), else
    the framework's (a copy: changing it changes nothing kept). None for a number that holds none."""
    found = fact(number)
    if found is None:
        return None
    if changed and number in changed:
        return copy.deepcopy(changed[number])
    return item_of(found)


def is_changed(number, made: mi.ModItem) -> bool:
    """Whether an item differs from the framework's own of that number: only one that does is kept and written."""
    found = fact(number)
    return found is None or made != item_of(found)


# =============================================================================
# (The twenty fifth session, 16 November 2026) One of the 40 as the Items page edits it
# =============================================================================
# Zodi's first point: the 40 "edited on the Items page". His choices: "Always listed (Recommended)" (every mod sees
# them after the game's items), and, for how one is edited, "I go with your recommendations": the New Content
# page's item sheet shown inside the Items page (`qt/pages/side_quests.ItemSheet`,
# `qt/pages/lion_items.LionItemPane`). The sheet edits a `mod_items.ItemEdit`; what the mod keeps of one of the 40 is
# its `ModItem` (`state.wotl_items`) and, where it gave it a picture of its own, that picture
# (`state.wotl_art`).

@dataclass
class Art:
    """A mod's own picture for one of the 40: its art (a PNG of the menus' size, `mod_items.ICON_SIZE`) and its
    small icon's (a PNG of `mod_items.SMALL_ICON_SIZE`; empty when it is made from the art), as an item of the mod's
    own keeps them (`mod_items.ItemEdit`)."""
    icon_png: bytes = b""
    small_png: bytes = b""


def near_icon(number) -> int:
    """The game's item whose icon stands for one of the 40 where an item must name one (the game's nearest item,
    whose look in battle it swings): 1 where that isn't one of the game's items."""
    found = fact(number)
    return found.near if found is not None and found.near in mi.GAME_ITEMS else 1


def own_picture(mod_id: str, number) -> str:
    """The name Mod Studio gives the files of a mod's own picture for one of the 40: of the mod and the item's
    number (`mod_items.icon_name`), so two mods' pictures for one item are two files."""
    return mi.icon_name(mod_id, f"wotl {int(number)}")


def own_icon_file(number, small: bool = False) -> Path:
    """The framework's own icon for one of the 40 (its art, or its small icon) as Mod Studio carries the framework
    (`event_setup.HELPER_FOLDER`, the files at the game's paths: `helper/build.py`'s `DATA`). Reached through the
    bundle's tools folder, which the built program's packing is checked to carry (`dev/test_frozen_paths.py` follows
    a read of the bundle by its folder: the first way written here, from the bundle's root by a name of another
    module's, was one it couldn't follow, and it said so)."""
    from . import event_setup as su
    return (paths.bundled_tools_dir() / Path(su.HELPER_FOLDER).name
            / mi.icon_files(icon_name(number))[2 if small else 0])


def uses_own_icon(number, made: mi.ModItem) -> bool:
    """Whether an item of the 40 shows the framework's own icon for its number (Zodi's art)."""
    return made.icon_picture == icon_name(number)


def edit_of(number, changed: Optional[dict] = None, art: Optional[dict] = None) -> Optional[mi.ItemEdit]:
    """One of the 40 as the sheet edits it: the item as the mod has it (`item`), the game's item its icon would be
    without one of its own, and the mod's own picture where it gave one (`art`: `state.wotl_art`). None for a
    number that holds none."""
    made = item(number, changed)
    if made is None:
        return None
    edit = mi.ItemEdit(str(int(number)), made, near_icon(number))
    own = (art or {}).get(number)
    if own is not None and own.icon_png:
        edit.icon_png, edit.small_png = bytes(own.icon_png), bytes(own.small_png)
        edit.item.icon, edit.item.icon_picture = edit.copied_from, ""
    return edit


def kept(number, edit: mi.ItemEdit) -> mi.ModItem:
    """
    The item as the mod keeps it (`state.wotl_items`): as it is written (`mod_items.written_item`: its bonuses none
    when they are all 0, its UI values set from what it does, the game's towns in their order), with the icon it
    shows: the framework's own for its number, one of the game's items', or, with a picture of the mod's own, no
    name yet (the picture's files are named of the mod as they are written: `written`) and the game's nearest
    item's number standing for it.
    """
    lion = not edit.icon_png and uses_own_icon(number, edit.item)
    made = mi.written_item(mi.ItemEdit(edit.folder, edit.item, edit.copied_from or near_icon(number)), "x")
    if lion:
        made.icon, made.icon_picture = 0, icon_name(number)
    elif edit.icon_png:
        made.icon, made.icon_picture = near_icon(number), ""
    return made


def written(number, made: mi.ModItem, art: Optional["Art"], mod_id: str) -> mi.ModItem:
    """The item as its mod's asking file gives it: as kept, a picture of the mod's own named of the mod and the
    item (`own_picture`)."""
    out = copy.deepcopy(made)
    if art is not None and art.icon_png:
        out.icon, out.icon_picture = 0, own_picture(mod_id, number)
    return out


def art_files(number, art: "Art", mod_id: str) -> dict:
    """The four files of a mod's own picture for one of the 40 (`mod_items.icon_files_of`), by their paths in the
    mod."""
    import io

    from PIL import Image
    small = Image.open(io.BytesIO(art.small_png)) if art.small_png else None
    return mi.icon_files_of(Image.open(io.BytesIO(art.icon_png)), own_picture(mod_id, number), small)


def items_text(changed: Optional[dict], art: Optional[dict] = None, mod_id: str = "") -> str:
    """The asking file's text for the mod's own versions (`{number: ModItem}`; none: the file only asks), each item
    as an `item.json` gives one with `"Item"` first, each list of bytes on one line; (the twenty fifth session) an
    item with a picture of the mod's own (`art`: `{number: Art}`) naming it (`written`)."""
    listed = []
    for number in sorted(changed or {}):
        fields = written(number, changed[number], (art or {}).get(number), mod_id).to_json()
        listed.append({"Item": int(number), **fields})
    out = {"Format": FORMAT, "Version": VERSION, "Items": listed}
    text = json.dumps(out, indent=2, ensure_ascii=False)
    return re.sub(r"\[\s+([\d,\s]+?)\s+\]", lambda m: "[" + " ".join(m.group(1).split()) + "]", text) + "\n"


def read_text(text: str, has_file=None) -> tuple:
    """
    (`{number: ModItem}`, problems) from the asking file's text, as the
    framework reads it (`WotLItems.Read`): a file that can't be used still
    asks and gives none (the framework's own stand); an item with a problem
    of its own is left out, each said in the helper's words (after the mod's
    and the file's names). An item's own icon may be the framework's for
    that number (`icon_name`: those files aren't asked of the mod), one of
    the game's items', or a picture of the mod's own (`has_file`).
    """
    has_file = has_file or (lambda _path: False)
    try:
        top = hj.loads(text)
    except ValueError as exc:
        return {}, [f"it isn't JSON ({exc})"]
    if not isinstance(top, dict) or hj.get(top, "Format") != FORMAT:
        return {}, [f"its Format isn't \"{FORMAT}\""]
    version = hj.get(top, "Version")
    if not isinstance(version, int) or isinstance(version, bool) or version != VERSION:
        return {}, [f"its Version isn't {VERSION}"]
    if not hj.has(top, "Items"):
        return {}, []
    listed = hj.get(top, "Items")
    if not isinstance(listed, list):
        return {}, ["its Items isn't a list"]
    changed, problems = {}, []
    for place, entry in enumerate(listed, 1):
        number = hj.get(entry, "Item") if isinstance(entry, dict) else None
        found = fact(number) if isinstance(number, int) and not isinstance(number, bool) else None
        if found is None:
            problems.append(f"its item {place} doesn't say which of War of the Lions' items it is (Item: one of "
                            f"their numbers, {FIRST} to {LAST})")
            continue
        own = mi.icon_files(icon_name(number))
        made, said = mi.read_item_text(json.dumps(entry, ensure_ascii=False),
                                       lambda path, own=own: path in own or has_file(path), never_sold=True)
        if made is not None and made.kind != found.kind:
            said, made = [f"its Kind isn't {found.name}'s ({mi.KINDS[found.kind]})"], None
        if made is not None and number in changed:
            said, made = ["the file gives it twice"], None
        problems.extend(f"{OWNER} item {number} ({found.name}): {why}" for why in said)
        if made is not None:
            changed[number] = made
    return changed, problems


def named_by(state) -> list:
    """The numbers of the 40 the mod names anywhere: on a unit of one of the game's battles or a buried treasure
    (`state.battle_units`, `state.battle_treasures`), or on a unit of one of its quests' own battles (a quest's
    battle's Items: `quest_edits`), each once, in order."""
    from . import mod_battles as mb
    refs = mb.items_named(getattr(state, "battle_units", None), getattr(state, "battle_treasures", None))
    for edits in (getattr(state, "quests", None) or {}).values():
        for battle in getattr(getattr(edits, "quest", None), "battles", None) or ():
            for worn in (getattr(battle, "items", None) or {}).values():
                refs.extend(worn.values())
    return [number for number in mb.lion_items(refs) if fact(number) is not None]


def asked_by(state) -> bool:
    """Whether the mod asks the framework for the 40: it names one anywhere (`named_by`) or has its own version
    of one (`state.wotl_items`). Its asking file is written then (`write`)."""
    return bool(getattr(state, "wotl_items", None)) or bool(named_by(state))


def read(mod_root) -> tuple:
    """(whether the mod asks for the 40, `{number: ModItem}`, problems) of a mod's asking file (`FILE` at its
    root): (False, {}, []) when it has none."""
    root = Path(mod_root)
    path = root / FILE
    if not path.is_file():
        return False, {}, []
    try:
        text = hj.read_text(path)
    except OSError as exc:
        return True, {}, [f"it can't be read ({exc})"]
    changed, problems = read_text(text, lambda rel: (root / rel).is_file())
    return True, changed, problems


def named_files(mod_root) -> list:
    """The files (from the mod's folder) of the pictures of the mod's own its asking file names for the 40; none
    when it has no such file, it can't be read, or it names none (the framework's own icons' files aren't the
    mod's)."""
    try:
        top = hj.loads(hj.read_text(Path(mod_root) / FILE))
    except (OSError, ValueError):
        return []
    listed = hj.get(top, "Items") if isinstance(top, dict) else None
    out = []
    for entry in listed if isinstance(listed, list) else ():
        if not isinstance(entry, dict):
            continue
        number, icon = hj.get(entry, "Item"), hj.get(entry, "Icon")
        if isinstance(icon, str) and mi.good_picture(icon) and icon != (
                icon_name(number) if isinstance(number, int) and not isinstance(number, bool) else None):
            out.extend(mi.icon_files(icon))
    return out


def read_art(mod_root, changed: dict) -> tuple:
    """
    (`{number: Art}`, problems, the files read) for the items of `changed` (as `read` gives them) that name a
    picture of the mod's own: its four files read back from the mod (`mod_items.icon_files`), the small one kept
    only where it isn't the one made from the art (as `mod_items.read_mod` reads an item's own icon). Each such
    item is left, in `changed`, as the mod keeps one with a picture of its own (`kept`), and its files are the
    item's now (Export writes them again). An item whose picture can't be read here is said and keeps the name it
    gives (its files stay the mod's, carried through).
    """
    from . import texture_data as td
    art, problems, files = {}, [], []
    for number in sorted(changed):
        made = changed[number]
        if not made.icon_picture or uses_own_icon(number, made):
            continue
        try:
            paths_ = mi.icon_files(made.icon_picture)
            image = td.decode_tex_in_process(Path(mod_root) / paths_[0])
            own = Art(mi.icon_png(image))
            small = td.decode_tex_in_process(Path(mod_root) / paths_[2]).convert("RGBA")
            if small.size != mi.SMALL_ICON_SIZE or small.tobytes() != mi.small_of(image).tobytes():
                own.small_png = mi.icon_png(small, mi.SMALL_ICON_SIZE)
        except Exception as exc:                                      # noqa: BLE001
            problems.append(f"{OWNER} item {number}: its own picture can't be read here ({exc})")
            continue
        art[number] = own
        files.extend(paths_)
        made.icon, made.icon_picture = near_icon(number), ""
    return art, problems, files


def write(mod_root, asked: bool, changed: Optional[dict], art: Optional[dict] = None, mod_id: str = "") -> list:
    """The asking file written into the mod when the mod names or changes one of the 40 (`asked`, or any in
    `changed`), else taken away; (the twenty fifth session) with it the files of each picture of the mod's own
    (`art`, `art_files`). Returns the paths written."""
    root = Path(mod_root)
    path = root / FILE
    # The pictures an earlier export wrote go first (one put aside since, or named of another mod id).
    for rel in named_files(root):
        if (root / rel).is_file():
            (root / rel).unlink()
    if not asked and not changed:
        if path.is_file():
            path.unlink()
        return []
    art = {number: own for number, own in (art or {}).items() if number in (changed or {}) and own.icon_png}
    path.write_text(items_text(changed, art, mod_id), encoding="utf-8")
    out = [FILE]
    for number in sorted(art):
        for rel, data in art_files(number, art[number], mod_id).items():
            (root / rel).parent.mkdir(parents=True, exist_ok=True)
            (root / rel).write_bytes(data)
            out.append(rel)
    return out
