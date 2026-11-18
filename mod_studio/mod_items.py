"""
(1.26.0) A mod's own items (Zodi's list of 3 November, his first: "Adding new
items to go into the new towns outfitter"; his choices: new items now, made on
the Side Quests page's Items tab, an icon of the game's or a texture of the
modder's own, a new item started as a copy of one of the game's).

**An item** is a folder of its own in a mod, `ModStudioItems/<item>/`,
holding `item.json`, read here as Mod Studio Framework reads it
(`helper/ModStudioEventSetup/ItemFile.cs`), each problem said in its words:

- `Name`: the item's name in its mod (letters and digits of English, spaces,
  underscores, hyphens and apostrophes, 1 to 64), the name a town's Outfitter
  sells it by (its place.json's Menu's Shop);
- `Kind`: Weapon, Shield, Head, Body, Accessory or Item;
- `Record`: its 12 bytes as the game keeps an item's (palette, graphic, level,
  type flags, its kind's record's number, its category, a byte, its equipment
  bonus row, its price in two bytes, the story point the shops sell it from, a
  byte), its kind's type flag set; `KindRecord`, its kind's record (a weapon's
  8 bytes, an item's 3, the others' 2); a weapon's or a shield's `SpritePair`
  (2 bytes); `Bonus`, its equipment bonuses' 26 bytes or none;
- `Words`: its Name, and if it has them its Singular, Plural and Description,
  given to the game's Item table as it loads;
- `Icon`: one of the game's items' icons by its number (1 to 253, 256 to
  260), or its own texture's files' name (its four files under
  `FFTIVC/data/enhanced/ui/ffto/icon/`: `icon_files`);
- `UiCategory` and `Sort`, as the game item it was copied from has them in
  the Item table (the menus' tabs and their order);
- (1.27.0) `Shops`: the game's towns whose Outfitters sell it too, each by
  its place (0 to 14: `GAME_TOWNS`), none when it has none; `UiStatus` and
  `RandomDamage`, its Item table row's UI status effect and random damage,
  which Mod Studio sets from what the item does as the game's own rows have
  them (`ui_values`), never typed.

The helper numbers each item past the game's and WotL Restoration's (316 to
381, `Numbers.json`'s `Items`): a modder never chooses a number, and Mod
Studio writes none.

**A copy of one of the game's items** (`GameItems`): the game's program read
as data (never run), its items' records found through the nine small
functions the game asks them of (their code found by its bytes, the tables'
places read from it), as `dev/research/sidequests/items.py` measured them.

Nothing here imports Qt.
"""
from __future__ import annotations

import copy
import json
import re
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from . import helper_json as hj

#: Where a mod keeps its items, one folder each; the file each holds (the helper's `ItemFile`).
FOLDER = "ModStudioItems"
FILE_NAME = "item.json"
FORMAT = "Mod Studio item"
VERSION = 1
NAME_MOST, WORD_MOST, DESCRIPTION_MOST = 64, 64, 400
#: The game's items an icon may be one of (IsValidItem's 1 to 253 and 256 to 260).
MOST_GAME_ITEM = 260
GAME_ITEMS = tuple(list(range(1, 254)) + list(range(256, 261)))
KINDS = ("Weapon", "Shield", "Head", "Body", "Accessory", "Item")
WEAPON, SHIELD, HEAD, BODY, ACCESSORY, ITEM = range(6)
#: Each kind in words, as a sentence says it (the helper's `KindWords`).
KIND_WORDS = ("a weapon", "a shield", "an item worn on the head", "an item worn on the body", "an accessory",
              "an item to use")
#: Each kind's record's bytes (the game's kind tables: ItemWeapon 8, ItemShield 2, ItemArmor 2 for a head and a body,
#: ItemAccessory 2, ItemChemist 3) and its type flag in its record's + 3.
KIND_BYTES = (8, 2, 2, 2, 2, 3)
KIND_FLAGS = (0x80, 0x40, 0x20, 0x10, 0x08, 0)
RECORD_BYTES, BONUS_BYTES, PAIR_BYTES = 12, 26, 2
KIND_MASK = 0xF8
#: The story point (the record's + 10) the shops sell an item from: 1 to 16, as the game's scenes go.
MOST_SHOP_POINT = 16
PRICE_AT, SHOP_AT, FLAGS_AT, KIND_AT, BONUS_AT = 8, 10, 3, 4, 7
#: Where an item's own icon's files are in its mod, and the size of each texture (the game's: the menus' 100 x 100,
#: the small one 48 x 48, each part list's TexturePart as the game's own lists have it).
ICON_FOLDER = "FFTIVC/data/enhanced/ui/ffto/icon"
ICON_SIZE, SMALL_ICON_SIZE = (100, 100), (48, 48)
ICON_PART, SMALL_ICON_PART = (0, 0, 96, 192), (0, 0, 96, 96)
#: (1.27.0) The game's 15 towns an item may be sold at besides its mod's own, by their places (0 to 14), as the game's
#: English PlaceName rows name them (the helper's `ItemRoom.TownNames`).
GAME_TOWNS = ("Royal City of Lesalia", "Riovanes Castle", "Eagrose Castle", "Lionel Castle", "Limberry Castle",
              "Zeltennia Castle", "Magick City of Gariland", "Walled City of Yardrow", "Mining Town of Gollund",
              "Merchant City of Dorter", "Castled City of Zaland", "Clockwork City of Goug", "Port City of Warjilis",
              "Free City of Bervenia", "Trade City of Sal Ghidos")
LAST_TOWN = len(GAME_TOWNS) - 1
#: (1.27.0) The most an item's UiStatus may be (the helper's `ItemFile.MostUiStatus`).
MOST_UI_STATUS = 65535
#: (1.27.0) Where a weapon's kind record keeps its formula, its Inflict Status (or, with the formula that casts a spell,
#: the spell's ability) and its elements (FFTPatcher's Weapon: Formula + 2, Elements + 6, InflictStatus + 7).
FORMULA_AT, ELEMENTS_AT, INFLICT_AT = 2, 6, 7
#: The weapon formula that casts a spell: its Inflict Status byte then names an ability.
CAST_SPELL_FORMULA = 2
#: (1.27.0) The equipment bonus row's statuses, each five bytes (FFTPatcher's ItemAttributes: the permanent ones + 5,
#: the immunities + 10, the starting ones + 15) and its elements, a byte each (absorbed + 20, cancelled + 21, halved
#: + 22, weak + 23, strengthened + 24).
STATUS_SETS_AT = (5, 10, 15)
ELEMENT_SETS_AT = (20, 21, 22, 23, 24)
#: (1.27.0) The game's own rows' UI status effect and random damage, from what an item does (all 258 of the game's
#: items have them so: dev/test_side_quests.py holds the rule to each): a weapon whose formula takes the hit points it
#: does (6, the Blood Sword's and the Bloodstring Harp's) 1001, one that heals by them (7, the Healing Staff's) 1002;
#: random damage for a weapon of the axes, flails and bags (categories 6, 9 and 17), or one whose formula casts by its
#: element (4, the magic guns').
UI_STATUS_OF_FORMULA = {6: 1001, 7: 1002}
RANDOM_CATEGORIES, RANDOM_FORMULA = (6, 9, 17), 4
CATEGORY_AT = 5


def good_name(name) -> bool:
    """An item's name (the helper's `ItemFile.GoodName`): letters and digits of English, spaces, underscores,
    hyphens and apostrophes, 1 to 64 of them, with no space at either end."""
    return (isinstance(name, str) and 0 < len(name) <= NAME_MOST and name.strip() == name
            and all(c.isascii() and (c.isalnum() or c in " _-'") for c in name))


def good_picture(name) -> bool:
    """An own icon's files' name: small letters, digits and _, 1 to 64 of them (as a place's own texture's)."""
    return isinstance(name, str) and re.fullmatch(r"[a-z0-9_]{1,64}", name) is not None


def icon_files(picture: str) -> list:
    """Where an item's own icon's textures and part lists are in its mod (the helper's `IconFiles`): the menus' and
    the small one's."""
    return [f"{ICON_FOLDER}/equip_item/texture/{picture}.tex",
            f"{ICON_FOLDER}/equip_item/textureparts/{picture}.utexpt",
            f"{ICON_FOLDER}/equip_item_s/texture/{picture}_s.tex",
            f"{ICON_FOLDER}/equip_item_s/textureparts/{picture}_s.utexpt"]


def icon_name(mod_id: str, folder: str) -> str:
    """The name Mod Studio gives an item's own icon's files: of the mod and the item (`msq_<mod>_<item>__icon`, two
    `_` together as no place's picture or art has them, `map_places.picture_name`), at most 62 (its small one's two
    more)."""
    def safe(text: str) -> str:
        return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_") or "x"
    return f"msq_{safe(mod_id)}_{safe(folder)}"[:62 - len("__icon")] + "__icon"


def folder_for(name: str) -> str:
    """The folder an item is written in: its name without apostrophes (a folder's name is letters, digits, spaces,
    underscores and hyphens)."""
    return " ".join(name.replace("'", "").split()) or "Item"


def free_name(wanted: str, taken) -> str:
    """`wanted`, or it numbered past the names `taken` ("Moon Sword 2"), as an item's name may be."""
    stem = " ".join("".join(ch if good_name(ch) else " " for ch in wanted).split())[:58] or "New Item"
    lowered = {folder_for(t).lower() for t in taken}
    if folder_for(stem).lower() not in lowered:
        return stem
    n = 2
    while folder_for(f"{stem} {n}").lower() in lowered:
        n += 1
    return f"{stem} {n}"


@dataclass
class ModItem:
    """An item as its file gives it (see the module's notes). `icon` is a game item's number, or 0 when it has its
    own (`icon_picture`); `ui_category` and `sort` are -1 when the file gives none; (1.27.0) `shops` the game's towns
    that sell it too (their places), `ui_status` and `random_damage` its row's UI values."""
    name: str
    kind: int
    record: bytes
    kind_record: bytes
    sprite_pair: bytes = b""
    bonus: Optional[bytes] = None
    word_name: str = ""
    singular: str = ""
    plural: str = ""
    description: str = ""
    icon: int = 0
    icon_picture: str = ""
    ui_category: int = -1
    sort: int = -1
    shops: tuple = ()
    ui_status: int = 0
    random_damage: bool = False

    def to_json(self) -> dict:
        words = {"Name": self.word_name or self.name}
        for key, text in (("Singular", self.singular), ("Plural", self.plural), ("Description", self.description)):
            if text:
                words[key] = text
        out = {"Format": FORMAT, "Version": VERSION, "Name": self.name, "Kind": KINDS[self.kind],
               "Record": list(self.record), "KindRecord": list(self.kind_record)}
        if self.kind in (WEAPON, SHIELD):
            out["SpritePair"] = list(self.sprite_pair)
        out["Bonus"] = list(self.bonus) if self.bonus is not None else None
        out["Words"] = words
        out["Icon"] = self.icon_picture if self.icon_picture else self.icon
        if self.ui_category >= 0:
            out["UiCategory"] = self.ui_category
        if self.sort >= 0:
            out["Sort"] = self.sort
        if self.shops:
            out["Shops"] = list(self.shops)
        if self.ui_status:
            out["UiStatus"] = self.ui_status
        if self.random_damage:
            out["RandomDamage"] = True
        return out


def item_text(item: ModItem) -> str:
    """An item's `item.json`, as Mod Studio writes it (each list of bytes on one line)."""
    text = json.dumps(item.to_json(), indent=2, ensure_ascii=False)
    return re.sub(r"\[\s+([\d,\s]+?)\s+\]", lambda m: "[" + " ".join(m.group(1).split()) + "]", text) + "\n"


def _whole(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _raw(d: dict, name: str) -> str:
    """A field as the helper says it (its JSON, cut at 77 characters past 80), "nothing" when it isn't there."""
    if not hj.has(d, name):
        return "nothing"
    raw = json.dumps(hj.get(d, name), ensure_ascii=False)
    return raw[:77] + "..." if len(raw) > 80 else raw


def _bytes(d: dict, name: str, count: int) -> Optional[bytes]:
    value = hj.get(d, name)
    if not isinstance(value, list) or len(value) != count or not all(_whole(b) and 0 <= b <= 255 for b in value):
        return None
    return bytes(value)


def _word(words: dict, name: str, most: int, required: bool):
    """A word of the item's: (good, text) as the helper's `Word`."""
    if not hj.has(words, name):
        return (not required), ""
    value = hj.get(words, name)
    if not isinstance(value, str):
        return False, ""
    breaks = 0
    for ch in value:
        if ch == "\n":
            breaks += 1
        elif ord(ch) < 0x20 or 0x7F <= ord(ch) <= 0x9F:
            # .NET's char.IsControl.
            return False, ""
    good = (0 < hj.units(value) <= most and breaks <= (2 if most == DESCRIPTION_MOST else 0)
            and len(value.encode("utf-8")) < 1024)
    return good, value if good else ""


#: (Mod Studio Framework 2.0.0) The story point of an item no shop sells: War of the Lions' own for all 40 of its
#: items (`WotLItems.NeverSold`: past the game's 16), taken for those items alone (`read_item_text`'s `never_sold`).
NEVER_SOLD = 20


def read_item_text(text: str, has_file: Callable[[str], bool], never_sold: bool = False) -> tuple:
    """(the item, problems) from an `item.json`'s text, checked as the helper checks it (`ItemFile.Read`); the
    item is None when anything is wrong. `has_file` says whether the mod has a file (its path from the mod's
    folder). `never_sold` (2.0.0: one of War of the Lions' items, `wotl_items`): its story point may be
    `NEVER_SOLD` too."""
    try:
        top = hj.loads(text)
    except ValueError as exc:
        return None, [f"its {FILE_NAME} isn't JSON ({exc})"]
    if not isinstance(top, dict):
        return None, [f"its {FILE_NAME} isn't a list of fields"]
    if hj.broken_text(top):
        return None, [f"its {FILE_NAME} {hj.BROKEN_TEXT}"]
    if hj.get(top, "Format") != FORMAT:
        return None, [f"its Format isn't \"{FORMAT}\""]
    version = hj.get(top, "Version")
    if not _whole(version) or version != VERSION:
        return None, [f"its Version is {_raw(top, 'Version')}, not {VERSION}"]
    name = hj.get(top, "Name")
    if not good_name(name):
        return None, [f"its Name is 1 to {NAME_MOST} letters, digits, spaces, underscores, hyphens and apostrophes, "
                      f"with no space at either end, not {_raw(top, 'Name')}"]
    kind_text = hj.get(top, "Kind")
    if kind_text not in KINDS:
        return None, [f"its Kind is Weapon, Shield, Head, Body, Accessory or Item, not {_raw(top, 'Kind')}"]
    kind = KINDS.index(kind_text)
    record = _bytes(top, "Record", RECORD_BYTES)
    if record is None:
        return None, [f"its Record is its {RECORD_BYTES} bytes as the game keeps an item's (each 0 to 255), not "
                      f"{_raw(top, 'Record')}"]
    if (record[FLAGS_AT] & KIND_MASK) != KIND_FLAGS[kind]:
        return None, [f"its Record's type flags (byte 3: {record[FLAGS_AT]}) aren't those of {KIND_WORDS[kind]} "
                      f"({KIND_FLAGS[kind]}, with Rare 2 if it is rare)"]
    if record[SHOP_AT] < 1 or (record[SHOP_AT] > MOST_SHOP_POINT
                               and not (never_sold and record[SHOP_AT] == NEVER_SOLD)):
        return None, [f"its Record's story point the shops sell it from (byte 10) is 1 to {MOST_SHOP_POINT}"
                      + (f", or {NEVER_SOLD} for an item no shop sells" if never_sold else "")
                      + f", not {record[SHOP_AT]}"]
    kind_record = _bytes(top, "KindRecord", KIND_BYTES[kind])
    if kind_record is None:
        return None, [f"its KindRecord is the record of {KIND_WORDS[kind]}, {KIND_BYTES[kind]} bytes (each 0 to 255), "
                      f"not {_raw(top, 'KindRecord')}"]
    pair = b""
    if kind in (WEAPON, SHIELD):
        pair = _bytes(top, "SpritePair", PAIR_BYTES) or b""
        if len(pair) != PAIR_BYTES:
            return None, [f"its SpritePair is a weapon's or a shield's two bytes (each 0 to 255), not "
                          f"{_raw(top, 'SpritePair')}"]
    elif hj.has(top, "SpritePair"):
        return None, ["only a weapon or a shield has a SpritePair"]
    bonus = None
    if hj.has(top, "Bonus") and hj.get(top, "Bonus") is not None:
        bonus = _bytes(top, "Bonus", BONUS_BYTES)
        if bonus is None:
            return None, [f"its Bonus is its equipment bonuses' {BONUS_BYTES} bytes (each 0 to 255), or none, not "
                          f"{_raw(top, 'Bonus')}"]
    words = hj.get(top, "Words")
    if not isinstance(words, dict):
        return None, ["it has no Words (its Name, Singular, Plural and Description)"]
    said = [_word(words, "Name", WORD_MOST, True), _word(words, "Singular", WORD_MOST, False),
            _word(words, "Plural", WORD_MOST, False), _word(words, "Description", DESCRIPTION_MOST, False)]
    if not all(good for good, _text in said):
        return None, [f"its Words are its Name (1 to {WORD_MOST} characters), and if it has them its Singular and "
                      f"Plural (1 to {WORD_MOST}) and Description (1 to {DESCRIPTION_MOST}, at most two line breaks), "
                      f"each text"]
    word_name, singular, plural, description = (text for _good, text in said)
    icon_value = hj.get(top, "Icon")
    icon, own = 0, ""
    if isinstance(icon_value, str) and good_picture(icon_value):
        own = icon_value
    elif not _whole(icon_value) or icon_value not in GAME_ITEMS:
        return None, [f"its Icon is one of the game's items' icons (by its number: 1 to 253, or 256 to "
                      f"{MOST_GAME_ITEM}), or its own texture's files' name (small letters, digits and _, 1 to 64 of "
                      f"them), not {_raw(top, 'Icon')}"]
    else:
        icon = icon_value
    if own:
        missing = [path for path in icon_files(own) if not has_file(path)]
        if missing:
            return None, [f"its icon's texture files aren't in the mod ({', '.join(missing)})"]
    ui_category = sort = -1
    if hj.has(top, "UiCategory"):
        ui_category = hj.get(top, "UiCategory")
        if not _whole(ui_category) or not 0 <= ui_category <= 255:
            return None, [f"its UiCategory is the Item table's UI category of the game item it was copied from (0 to "
                          f"255), not {_raw(top, 'UiCategory')}"]
    if hj.has(top, "Sort"):
        sort = hj.get(top, "Sort")
        if not _whole(sort) or not 0 <= sort <= 999999:
            return None, [f"its Sort is the Item table's sort of the game item it was copied from (0 to 999999), not "
                          f"{_raw(top, 'Sort')}"]
    shops = []
    if hj.has(top, "Shops"):
        listed = hj.get(top, "Shops")
        good = isinstance(listed, list)
        if good:
            for town in listed:
                if not _whole(town) or not 0 <= town <= LAST_TOWN or town in shops:
                    good = False
                    break
                shops.append(town)
        if not good:
            return None, [f"its Shops are the game's towns whose Outfitters sell it, each by its number (0 to "
                          f"{LAST_TOWN}) and once, not {_raw(top, 'Shops')}"]
    ui_status = 0
    if hj.has(top, "UiStatus"):
        ui_status = hj.get(top, "UiStatus")
        if not _whole(ui_status) or not 0 <= ui_status <= MOST_UI_STATUS:
            return None, [f"its UiStatus is the Item table's UI status effect for what it does (0 to {MOST_UI_STATUS}), "
                          f"not {_raw(top, 'UiStatus')}"]
    random_damage = False
    if hj.has(top, "RandomDamage"):
        value = hj.get(top, "RandomDamage")
        if value is True:
            random_damage = True
        elif value is not False:
            return None, [f"its RandomDamage is true or false (the Item table's random damage), not "
                          f"{_raw(top, 'RandomDamage')}"]
    return ModItem(name, kind, record, kind_record, pair, bonus, word_name, singular or word_name,
                   plural or word_name, description, icon, own, ui_category, sort, tuple(shops), ui_status,
                   random_damage), []


def read_mod_items(mod_folder) -> list:
    """Every item of a mod, in its folders' order: (folder, the item or None, problems); an item named as an earlier
    one of the mod is left out (the helper's `ReadMod`)."""
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
        item, problems = read_item_text(text, lambda path: (Path(mod_folder) / path).is_file())
        if item is not None and item.name in names:
            item, problems = None, [f"another of the mod's items is named {item.name}"]
        if item is not None:
            names.add(item.name)
        out.append((sub.name, item, problems))
    return out


def item_names(mod_folder) -> list:
    """The names of a mod's items the helper would read, in their folders' order."""
    return [item.name for _folder, item, _problems in read_mod_items(mod_folder) if item is not None]


# =============================================================================
# An item edited on the Side Quests page
# =============================================================================

@dataclass
class ItemEdit:
    """One of the mod's items as the Side Quests page edits it: its folder, the item, the game item it was copied
    from (its number, 0 when not known: one read back from a mod) and its own icon's texture (a PNG of the menus'
    size, `ICON_SIZE`; empty when its icon is a game item's); (1.27.0) its own small icon's (a PNG of
    `SMALL_ICON_SIZE`; empty when it is made from the menus' one)."""
    folder: str
    item: ModItem
    copied_from: int = 0
    icon_png: bytes = b""
    icon_from: str = ""
    small_png: bytes = b""
    small_from: str = ""


def copied(items: dict) -> dict:
    """Copies of the page's items, for an export running beside the page."""
    return copy.deepcopy(items)


def item_named(items: dict, name: str) -> Optional[ItemEdit]:
    return next((e for e in items.values() if e.item.name == name), None)


def rename(edit: ItemEdit, name: str) -> None:
    """An item given another name (its words' name with it, when it was the same)."""
    if edit.item.word_name in ("", edit.item.name):
        edit.item.word_name = name
    if edit.item.singular == edit.item.name:
        edit.item.singular = name
    edit.item.name = name


def icon_files_of(image, picture: str, small=None) -> dict:
    """An own icon's four files (`icon_files`) from a picture (PIL): it fitted to the menus' size, and (1.27.0) the
    small one from `small` fitted to its size, or when none is given from the menus' one (`small_of`); each part list
    naming its texture as the game's do, its part 0 as theirs."""
    from . import texture_data as td
    from . import uib
    big = fitted_to(image, ICON_SIZE)
    small = fitted_to(small, SMALL_ICON_SIZE) if small is not None else small_of(big)
    out = {}
    paths = icon_files(picture)
    for (texture, parts), fitted, part, inner in (
            ((paths[0], paths[1]), big, ICON_PART, f"ui/ffto/icon/equip_item/texture/{picture}.tex"),
            ((paths[2], paths[3]), small, SMALL_ICON_PART, f"ui/ffto/icon/equip_item_s/texture/{picture}_s.tex")):
        out[texture] = td.rgba_tex(fitted)
        out[parts] = uib.part_list_file(inner, [("TexturePart", part)])
    return out


def fitted_to(image, size: tuple):
    """A picture (PIL) as RGBA at `size` (resized when it isn't)."""
    from PIL import Image
    image = image.convert("RGBA")
    return image if image.size == size else image.resize(size, Image.LANCZOS)


def small_of(big):
    """(1.27.0) The small icon made from the menus' one (a PIL picture of `ICON_SIZE`): it fitted to
    `SMALL_ICON_SIZE`, so reading a mod back can tell a small icon made so from one of its own (`read_mod`)."""
    return fitted_to(big, SMALL_ICON_SIZE)


def icon_png(image, size: tuple = ICON_SIZE) -> bytes:
    """A picture (PIL) fitted to an item icon's size (`ICON_SIZE`, the game's menus', or (1.27.0) the small one's,
    `SMALL_ICON_SIZE`), as a PNG."""
    import io
    out = io.BytesIO()
    fitted_to(image, size).save(out, "PNG")
    return out.getvalue()


def written_item(edit: ItemEdit, mod_id: str) -> ModItem:
    """The item as it is written: its own icon named of the mod and the item (`icon_name`), its bonuses none when
    they are all 0, (1.27.0) its UI values set from what it does (`ui_values`), the game's towns selling it in their
    order."""
    item = copy.deepcopy(edit.item)
    item.icon_picture = icon_name(mod_id, edit.folder) if edit.icon_png else ""
    if not item.icon_picture and item.icon not in GAME_ITEMS:
        item.icon = edit.copied_from if edit.copied_from in GAME_ITEMS else 1
    if item.bonus is not None and not any(item.bonus):
        item.bonus = None
    item.ui_status, item.random_damage = ui_values(item)
    item.shops = tuple(sorted(set(item.shops)))
    return item


def write_item(mod_root, mod_id: str, edit: ItemEdit) -> list:
    """Writes the item into `<mod_root>/ModStudioItems/<folder>/item.json`, and its own icon as its four files at the
    game's paths in the mod (`icon_files`). Returns the paths written."""
    import io

    from PIL import Image
    item = written_item(edit, mod_id)
    root = Path(mod_root)
    folder = root / FOLDER / edit.folder
    folder.mkdir(parents=True, exist_ok=True)
    (folder / FILE_NAME).write_text(item_text(item), encoding="utf-8")
    written = [f"{FOLDER}/{edit.folder}/{FILE_NAME}"]
    if item.icon_picture:
        small = Image.open(io.BytesIO(edit.small_png)) if edit.small_png else None
        for rel, data in icon_files_of(Image.open(io.BytesIO(edit.icon_png)), item.icon_picture, small).items():
            (root / rel).parent.mkdir(parents=True, exist_ok=True)
            (root / rel).write_bytes(data)
            written.append(rel)
    return written


def named_files(folder: Path) -> list:
    """The icon files (from the mod's folder) an item's file in `folder` names; none when it names none or can't be
    read."""
    try:
        top = hj.loads(hj.read_text(Path(folder) / FILE_NAME))
    except (OSError, ValueError):
        return []
    if not isinstance(top, dict):
        return []
    icon = hj.get(top, "Icon")
    return icon_files(icon) if isinstance(icon, str) and good_picture(icon) else []


def read_mod(mod_root) -> list:
    """The mod's items as the page has them: (folder, the edit or None, problems) in their folders' order, as Mod
    Studio Framework reads them; an own icon read back from the mod's files (one that can't be read here is a
    problem: the item is then carried through as it is)."""
    from . import texture_data as td
    out = []
    for folder, item, problems in read_mod_items(mod_root):
        if item is None:
            out.append((folder, None, problems))
            continue
        edit = ItemEdit(folder, item, item.icon if item.icon in GAME_ITEMS else 0)
        if item.icon_picture:
            try:
                paths = icon_files(item.icon_picture)
                image = td.decode_tex_in_process(Path(mod_root) / paths[0])
                edit.icon_png = icon_png(image)
                edit.icon_from = f"{item.icon_picture}.tex"
                # (1.27.0) Its small icon: its own unless it is the one made from the menus' (`small_of`).
                small = td.decode_tex_in_process(Path(mod_root) / paths[2]).convert("RGBA")
                if small.size != SMALL_ICON_SIZE or small.tobytes() != small_of(image).tobytes():
                    edit.small_png = icon_png(small, SMALL_ICON_SIZE)
                    edit.small_from = f"{item.icon_picture}_s.tex"
            except Exception as exc:                                  # noqa: BLE001
                out.append((folder, None, [f"its icon can't be read here ({exc})"]))
                continue
        out.append((folder, edit, []))
    return out


# =============================================================================
# The game's own items, from its program (read as data, never run)
# =============================================================================

class ItemsError(ValueError):
    """The game's items can't be read from a program; the message says why, in words."""


def _pattern(text: str):
    """A regular expression of bytes from hex, `?` for any byte, `(` `)` round the bytes a value is read from."""
    out = b""
    for token in text.split():
        if token == "??":
            out += b"."
        elif token == "(":
            out += b"("
        elif token == ")":
            out += b")"
        else:
            out += re.escape(bytes([int(token, 16)]))
    return re.compile(out, re.DOTALL)


#: The code the game asks its items' records of (`dev/research/sidequests/items.py`: ItemCommon 0x2B8C44, the first
#: number of an item's kind 0x2B8C0C, ItemWeapon 0x2B8C74, ItemShield 0x2B8CD4, ItemArmor 0x2B8D3C, ItemAccessory
#: 0x2B8DA0, ItemChemist 0x2B8E04, ItemSpritePair 0x2B8E60, and a reach of the equipment bonus rows, 0xFA7E2), each
#: found by its bytes, a table's place (from the program's start) read where each `( )` is: the PlayStation's table and
#: the remaster's.
_CODE = {
    "common": "0F B7 C1 BA 00 01 00 00 66 3B CA 48 8D 0D ?? ?? ?? ?? 48 8D 04 40 73 0A 48 8D 04 85 ( ?? ?? ?? ?? ) "
              "EB 08 48 8D 04 85 ( ?? ?? ?? ?? ) 48 03 C1 C3",
    "segments": "48 63 84 82 ( ?? ?? ?? ?? ) 48 63 8C 82 ( ?? ?? ?? ?? ) 0F B7 84 4A ( ?? ?? ?? ?? )",
    "weapon": "83 FA 05 75 18 49 8D 88 ( ?? ?? ?? ?? ) EB 07 49 8D 88 ( ?? ?? ?? ?? ) 41 0F B7 C2 48 8D 0C C1",
    "shield": "83 FA 05 75 1F 41 0F B7 C2 48 8D 04 45 ( ?? ?? ?? ?? ) 49 03 C0 EB 10 41 0F B7 C2 48 8D 04 45 "
              "( ?? ?? ?? ?? )",
    "armor": "83 F9 07 75 1F 41 0F B7 C2 48 8D 04 45 ( ?? ?? ?? ?? ) 48 03 C2 EB 10 41 0F B7 C2 48 8D 04 45 "
             "( ?? ?? ?? ?? )",
    "accessory": "83 F9 08 75 1F 41 0F B7 C2 48 8D 04 45 ( ?? ?? ?? ?? ) 48 03 C2 EB 10 41 0F B7 C2 48 8D 04 45 "
                 "( ?? ?? ?? ?? )",
    "chemist": "83 3C 81 09 75 1D 48 8D 0D ( ?? ?? ?? ?? ) 41 0F B7 C2 48 8D 04 40 48 03 C1 EB 0B 48 8D 0D "
               "( ?? ?? ?? ?? ) EB EA",
    "pair": "0F B7 C1 48 8D 04 45 ( ?? ?? ?? ?? ) 49 03 C1 EB 0F 0F B7 C1 48 8D 04 45 ( ?? ?? ?? ?? ) EB EE",
    "bonus": "80 78 07 55 73 14 0F B6 48 07 48 6B F9 1A 48 8D 0D ( ?? ?? ?? ?? ) 48 03 F9",
}
#: The kind of each of the game's ten kinds of record (0x67FB78's answers: 0 to 4 the PlayStation's weapons, shields,
#: armor, accessories and items, 5 to 9 the remaster's).
_TABLE_OF_KIND = ("weapon", "shield", "armor", "accessory", "chemist")
#: The code whose tables are reached by a distance from it (the rest by their places from the program's start).
_RIP = ("chemist", "bonus")
_ROW_BYTES = {"weapon": 8, "shield": 2, "armor": 2, "accessory": 2, "chemist": 3}


@dataclass
class GameItem:
    """One of the game's items as its program holds it: its kind (`KINDS`), its 12 byte record, its kind's record,
    a weapon's or a shield's sprite pair, and its equipment bonus row (None for row 0, which has none)."""
    number: int
    kind: int
    record: bytes
    kind_record: bytes
    sprite_pair: bytes
    bonus: Optional[bytes]


class GameItems:
    """The game's items 1 to 253 and 256 to 260 from its program's bytes (see the module's notes); ItemsError when
    its code isn't as measured (another version of the game)."""

    def __init__(self, data: bytes):
        from . import event_setup as su
        try:
            self._sections = su.sections(data)
        except su.SetupError as exc:
            raise ItemsError(f"the game's program can't be read ({exc})") from exc
        self._data = data
        code = next((s for s in self._sections if s.name == ".text"), None)
        if code is None:
            raise ItemsError("the game's program has no code")
        text = data[code.at:code.at + code.stored]
        found = {}
        for name, pattern in _CODE.items():
            matches = list(_pattern(pattern).finditer(text))
            if len(matches) != 1:
                raise ItemsError(f"the game's items can't be read from its program (its {name} code is found "
                                 f"{len(matches)} times, not once)")
            m = matches[0]
            values = []
            for g in range(1, (m.lastindex or 0) + 1):
                value = struct.unpack("<i", m.group(g))[0]
                if name in _RIP:
                    # lea rcx, [rip + d]: a distance from the instruction's end, just past its 4 bytes.
                    value += code.address + m.end(g)
                values.append(value)
            found[name] = values
        self._bonus = found["bonus"][0]
        self._common = found["common"]
        self._seg_kind, self._kind_first, self._bounds = found["segments"]
        self._tables = {name: found[name] for name in ("weapon", "shield", "armor", "accessory", "chemist", "pair")}

    def _at(self, address: int, length: int) -> bytes:
        from . import event_setup as su
        at = su.file_offset(self._sections, address)
        if at is None or at + length > len(self._data):
            raise ItemsError(f"the game's items can't be read from its program (0x{address:X} isn't in it)")
        return self._data[at:at + length]

    def _i32(self, address: int) -> int:
        return struct.unpack("<i", self._at(address, 4))[0]

    def segment(self, number: int) -> int:
        """SecondaryItemType's answer: the segment an item's number is in (-1 for none)."""
        if number > 0xFD and not 0 <= number - 0x100 <= 4:
            return -1
        bounds = struct.unpack("<14H", self._at(self._bounds, 28))
        for seg in range(13):
            if number < bounds[seg + 1]:
                return seg
        return -1

    def item(self, number: int) -> GameItem:
        if number not in GAME_ITEMS:
            raise ItemsError(f"{number} isn't one of the game's items")
        seg = self.segment(number)
        if seg < 0:
            raise ItemsError(f"the game's item {number} has no kind in its program")
        kind10 = self._i32(self._seg_kind + 4 * seg)
        first_seg = self._i32(self._kind_first + 4 * kind10)
        first = struct.unpack("<H", self._at(self._bounds + 2 * first_seg, 2))[0]
        table = _TABLE_OF_KIND[kind10 % 5]
        remaster = kind10 >= 5
        kind = {"weapon": WEAPON, "shield": SHIELD, "accessory": ACCESSORY, "chemist": ITEM}.get(table)
        if table == "armor":
            kind = HEAD if seg == first_seg else BODY
        low, high = self._common
        record = self._at((low + 12 * number) if number < 0x100 else (high + 12 * number), RECORD_BYTES)
        places = self._tables[table]
        # The weapon's code names the remaster's table first, the others theirs first too (see _CODE).
        kind_record = self._at((places[0] if remaster else places[1]) + _ROW_BYTES[table] * (number - first),
                               _ROW_BYTES[table])
        pair = b""
        if table in ("weapon", "shield"):
            pairs = self._tables["pair"]
            pair = self._at((pairs[0] if remaster else pairs[1]) + 2 * number, PAIR_BYTES)
        row = record[BONUS_AT]
        bonus = self._at(self._bonus + BONUS_BYTES * row, BONUS_BYTES) if row else None
        return GameItem(number, kind, record, kind_record, pair, bonus)


_programs: dict = {}


def game_items(path) -> GameItems:
    """The game's items from the program at `path`, read once for each size and time of the file. OSError when it
    can't be read, ItemsError when its items can't be found."""
    path = Path(path)
    stat = path.stat()
    key = (str(path), stat.st_size, stat.st_mtime_ns)
    if key not in _programs:
        _programs.clear()
        _programs[key] = GameItems(path.read_bytes())
    return _programs[key]


def copy_of(game: GameItem, name: str, words: Optional[dict] = None, ui_category: int = -1,
            sort: int = -1) -> ModItem:
    """A new item: a copy of one of the game's (its records, its kind's type flag set as the kind's own), named
    `name`, its words the game item's (`words`: the Item table's Singular, Plural and Description) but its name, its
    icon the game item's, its menus' tab and order the game item's."""
    record = bytearray(game.record)
    record[FLAGS_AT] = (record[FLAGS_AT] & ~KIND_MASK & 0xFF) | KIND_FLAGS[game.kind]
    if not 1 <= record[SHOP_AT] <= MOST_SHOP_POINT:
        record[SHOP_AT] = 1
    words = words or {}
    description = words.get("Description", "") or ""
    if len(description) > DESCRIPTION_MOST or description.count("\n") > 2:
        description = ""
    item = ModItem(name, game.kind, bytes(record), bytes(game.kind_record), bytes(game.sprite_pair),
                   bytes(game.bonus) if game.bonus is not None else None, name, name, name, description,
                   game.number, "", ui_category, sort)
    item.ui_status, item.random_damage = ui_values(item)
    return item


def ui_values(item: ModItem) -> tuple:
    """(1.27.0) (its UI status effect, its random damage) as the game's own Item rows have them for what an item does
    (`UI_STATUS_OF_FORMULA`, `RANDOM_CATEGORIES`, `RANDOM_FORMULA`: a weapon's formula and category; every other kind
    0 and none)."""
    if item.kind != WEAPON or len(item.kind_record) <= FORMULA_AT:
        return 0, False
    formula = item.kind_record[FORMULA_AT]
    return (UI_STATUS_OF_FORMULA.get(formula, 0),
            item.record[CATEGORY_AT] in RANDOM_CATEGORIES or formula == RANDOM_FORMULA)


# =============================================================================
# The numbers an item's card shows
# =============================================================================

#: The numbers an item's card shows, by kind (Mod Studio's Items page's labels: `constants.ITEM_XML_NUMERIC_FIELDS`):
#: (label, where: "record", "kind" or "bonus", its byte, its bytes, the most it may be).
NUMBERS = {
    WEAPON: [("Power", "kind", 4, 1, 255), ("Evasion", "kind", 5, 1, 255), ("Range", "kind", 0, 1, 255)],
    SHIELD: [("Physical Evasion", "kind", 0, 1, 255), ("Magical Evasion", "kind", 1, 1, 255)],
    HEAD: [("HP Bonus", "kind", 0, 1, 255), ("MP Bonus", "kind", 1, 1, 255)],
    BODY: [("HP Bonus", "kind", 0, 1, 255), ("MP Bonus", "kind", 1, 1, 255)],
    ACCESSORY: [("Physical Evasion", "kind", 0, 1, 255), ("Magical Evasion", "kind", 1, 1, 255)],
    ITEM: [("Power", "kind", 1, 1, 255)],
}
PRICE = ("Price", "record", PRICE_AT, 2, 65535)
BONUSES = [("PA Bonus", "bonus", 0, 1, 255), ("MA Bonus", "bonus", 1, 1, 255), ("Speed Bonus", "bonus", 2, 1, 255),
           ("Move Bonus", "bonus", 3, 1, 255), ("Jump Bonus", "bonus", 4, 1, 255)]


def number(item: ModItem, where: str, at: int, width: int) -> int:
    raw = {"record": item.record, "kind": item.kind_record, "bonus": item.bonus or bytes(BONUS_BYTES)}[where]
    return int.from_bytes(raw[at:at + width], "little")


def set_number(item: ModItem, where: str, at: int, width: int, value: int) -> None:
    """One of the item's numbers set (an equipment bonus given its row of bonuses, all 0 but it, if it had none)."""
    value = max(0, min(int(value), (1 << (8 * width)) - 1))
    if where == "record":
        raw = bytearray(item.record)
    elif where == "kind":
        raw = bytearray(item.kind_record)
    else:
        raw = bytearray(item.bonus or bytes(BONUS_BYTES))
    raw[at:at + width] = value.to_bytes(width, "little")
    if where == "record":
        item.record = bytes(raw)
    elif where == "kind":
        item.kind_record = bytes(raw)
    else:
        item.bonus = bytes(raw)


#: (Zodi after test 62) The record's first two bytes: the palette and the sprite of the icon a unit holds up or throws
#: in battle (the Items page's Sprite and Palette; ITEM.BIN's icon, g2d.dat's 158 enhanced).
HELD_PALETTE_AT, HELD_SPRITE_AT = 0, 1


def held(item: ModItem) -> tuple:
    """(Zodi after test 62) (its palette, its sprite): the icon a unit holds up or throws in battle."""
    return item.record[HELD_PALETTE_AT], item.record[HELD_SPRITE_AT]


def set_held(item: ModItem, palette: int, sprite: int) -> None:
    """(Zodi after test 62) The icon a unit holds up or throws in battle: its palette and its sprite."""
    raw = bytearray(item.record)
    raw[HELD_PALETTE_AT], raw[HELD_SPRITE_AT] = int(palette) & 0xFF, int(sprite) & 0xFF
    item.record = bytes(raw)


def first_of_categories(game: "GameItems") -> list:
    """(Zodi after test 62: "when creating a new item it gave you a prompt to enter the Name of the item and the
    Category of the Item") `[(category, number)]`: each category the game's items have, but items to use, in the
    categories' order, with the game's first item of it (by its number), whose numbers a new item of it starts
    with."""
    first = {}
    for number in GAME_ITEMS:
        try:
            game_item = game.item(number)
        except ItemsError:
            continue
        if game_item.kind == ITEM:
            continue
        first.setdefault(game_item.record[CATEGORY_AT], number)
    return sorted(first.items())


def shop_point(item: ModItem) -> int:
    return item.record[SHOP_AT]


def set_shop_point(item: ModItem, point: int, never_sold: bool = False) -> None:
    """The story point (1 to 16) the shops sell the item from; (2.0.0) `never_sold`: or `NEVER_SOLD`, for one of War
    of the Lions' items (`read_item_text`'s rule of the same name)."""
    raw = bytearray(item.record)
    raw[SHOP_AT] = (NEVER_SOLD if never_sold and int(point) == NEVER_SOLD
                    else max(1, min(int(point), MOST_SHOP_POINT)))
    item.record = bytes(raw)


# =============================================================================
# (1.27.0) What an item's card sets besides its numbers (Zodi's observations of 3 November, after test 58)
# =============================================================================

def _named_bits(raw: bytes, names: list) -> list:
    """The names whose bits are set in `raw`, eight to a byte, the first named its first byte's 0x80 (as the game's
    status and element bytes are laid out: `constants.STATUS_GROUPS`, `constants.ELEMENT_FLAGS`)."""
    return [name for n, name in enumerate(names) if raw[n // 8] & (0x80 >> (n % 8))]


def _bits_of(names_set, names: list, kept: bytes) -> bytes:
    """`kept` with the bits of `names` set as `names_set` has them (any bit not named left as it was)."""
    raw = bytearray(kept)
    for n, name in enumerate(names):
        bit = 0x80 >> (n % 8)
        if name in names_set:
            raw[n // 8] |= bit
        else:
            raw[n // 8] &= ~bit & 0xFF
    return bytes(raw)


def formula(item: ModItem) -> int:
    """A weapon's formula (its kind record's `FORMULA_AT`), -1 for any other kind."""
    return item.kind_record[FORMULA_AT] if item.kind == WEAPON else -1


def casts_spell(item: ModItem) -> bool:
    """Whether a weapon's formula casts a spell (its Inflict Status byte then names an ability)."""
    return formula(item) == CAST_SPELL_FORMULA


def set_kind_byte(item: ModItem, at: int, value: int) -> None:
    raw = bytearray(item.kind_record)
    raw[at] = max(0, min(int(value), 255))
    item.kind_record = bytes(raw)


def set_formula(item: ModItem, value: int) -> None:
    """A weapon's formula set (its UI values follow it as the item is written: `ui_values`)."""
    if item.kind == WEAPON:
        set_kind_byte(item, FORMULA_AT, value)
        item.ui_status, item.random_damage = ui_values(item)


def inflict(item: ModItem) -> int:
    """A weapon's Inflict Status row, or with the formula that casts a spell, the spell's ability; -1 for any other
    kind."""
    return item.kind_record[INFLICT_AT] if item.kind == WEAPON else -1


def set_inflict(item: ModItem, value: int) -> None:
    if item.kind == WEAPON:
        set_kind_byte(item, INFLICT_AT, value)


def weapon_elements(item: ModItem) -> list:
    """A weapon's elements (`constants.ELEMENT_FLAGS`' names)."""
    from . import constants as c
    return _named_bits(item.kind_record[ELEMENTS_AT:ELEMENTS_AT + 1], c.ELEMENT_FLAGS) if item.kind == WEAPON else []


def set_weapon_elements(item: ModItem, names) -> None:
    from . import constants as c
    if item.kind == WEAPON:
        set_kind_byte(item, ELEMENTS_AT, _bits_of(set(names), c.ELEMENT_FLAGS,
                                                  item.kind_record[ELEMENTS_AT:ELEMENTS_AT + 1])[0])


def bonus_statuses(item: ModItem, which: int) -> list:
    """The statuses of one of its equipment bonus row's three sets (`which`: 0 the ones it always has, 1 those it is
    immune to, 2 those it starts a battle with: `STATUS_SETS_AT`), by `constants.STATUS_FLAGS`' names."""
    from . import constants as c
    at = STATUS_SETS_AT[which]
    return _named_bits((item.bonus or bytes(BONUS_BYTES))[at:at + 5], c.STATUS_FLAGS)


def set_bonus_statuses(item: ModItem, which: int, names) -> None:
    """One of its bonus row's status sets set (the row made, all 0 but it, if it had none)."""
    from . import constants as c
    at = STATUS_SETS_AT[which]
    raw = bytearray(item.bonus or bytes(BONUS_BYTES))
    raw[at:at + 5] = _bits_of(set(names), c.STATUS_FLAGS, bytes(raw[at:at + 5]))
    item.bonus = bytes(raw)


def bonus_elements(item: ModItem, which: int) -> list:
    """The elements of one of its bonus row's five sets (`which`: 0 absorbed, 1 cancelled, 2 halved, 3 weak to,
    4 strengthened: `ELEMENT_SETS_AT`)."""
    from . import constants as c
    at = ELEMENT_SETS_AT[which]
    return _named_bits((item.bonus or bytes(BONUS_BYTES))[at:at + 1], c.ELEMENT_FLAGS)


def set_bonus_elements(item: ModItem, which: int, names) -> None:
    from . import constants as c
    at = ELEMENT_SETS_AT[which]
    raw = bytearray(item.bonus or bytes(BONUS_BYTES))
    raw[at:at + 1] = _bits_of(set(names), c.ELEMENT_FLAGS, bytes(raw[at:at + 1]))
    item.bonus = bytes(raw)


def set_shops(item: ModItem, towns) -> None:
    """The game's towns (their places, 0 to `LAST_TOWN`) whose Outfitters sell it, in their order."""
    item.shops = tuple(sorted({int(t) for t in towns if 0 <= int(t) <= LAST_TOWN}))


# =============================================================================
# (1.27.0) A weapon's look in battle (Zodi's second observation of 3 November: "the in game attacking animation
# texture"; his choice: "A game weapon's look")
# =============================================================================

#: The weapon's swing in battle is drawn from its sprite pair (`ItemSpritePair`, `0x2B8E60`, read only by the swing's
#: palette load `0x26A358` and its animation `0x26BC60`): its first byte's high four bits one of the 16 palettes of the
#: game's one weapon page (WEP.SPR's; the enhanced look's page is g2d texture 161), its low four bits a second palette
#: loaded with it, its second byte the picture's row on that page (eight pixels a row) in its type's column. The
#: Items page's Palette and SpriteID (the record's first two bytes) draw only its classic icon, never its swing. The
#: game's weapon types whose swings share their frames (so one column): the ninja blades, swords, knight swords,
#: katanas, rods and staves; the axes and flails; the spears and poles; every other type its own.
BATTLE_FAMILIES = ((2, 3, 4, 5, 7, 8), (6, 9), (15, 16))
PALETTES = 16
#: (Zodi, 4 November: "Palette 1 and 2 look very corrupted") The palettes the game's own weapons swing in, measured in
#: his program over its 129 weapons' sprite pairs (`swing_palettes`): 0 and 3 to 15. None of them swings in 1 or 2;
#: 20 of them carry 1 or 2 as their second palette (the pair's low four bits), beside their own. So a weapon's look is
#: offered in these alone (one read from a file in 1 or 2 is still shown as it is).
SWING_PALETTES = (0,) + tuple(range(3, PALETTES))
#: (Zodi, 5 November: "for shields I can not change the look of or the palette of the Guard sprite only the Held or
#: thrown sprite") A shield guards with its sprite pair as a weapon swings with its own (fft_decomp's
#: `sprite_thrown_item_palette_set` gives the weapon block the item's type, a shield's frames 383 to 388 of the
#: shields' type, 19): its row on the same weapons' texture, colored by one of the same 16 palettes. Measured in his
#: program: the game's 16 shields guard with two looks (rows 0 and 6) in palettes 3, 5, 6, 7, 8, 10, 13, 14 and 15,
#: none in 1 or 2; a shield's look is offered in `SWING_PALETTES` too (`guard_palettes` is what it was measured from).


def battle_family(category: int) -> tuple:
    """The weapon types (their categories, the record's + 5) whose swings look as `category`'s may; (the thirty third
    session) a fell sword's (War of the Lions' type 0x23) the swords', whose frames the game draws it with
    (`unit_sprites.FELL_SWORD`)."""
    from .unit_sprites import FELL_SWORD, FELL_SWORD_FRAMES
    if category == FELL_SWORD:
        category = FELL_SWORD_FRAMES
    return next((f for f in BATTLE_FAMILIES if category in f), (category,))


def battle_palette(item: ModItem) -> int:
    """A weapon's or (5 November) a shield's palette in battle (0 to 15), -1 for any other kind."""
    return item.sprite_pair[0] >> 4 if item.kind in (WEAPON, SHIELD) and len(item.sprite_pair) == PAIR_BYTES else -1


def set_battle_look(item: ModItem, pair: bytes) -> None:
    """A weapon's (or shield's) look in battle that of the game weapon (or shield) whose sprite pair is `pair` (its
    picture, its palettes)."""
    if item.kind in (WEAPON, SHIELD) and len(pair) == PAIR_BYTES:
        item.sprite_pair = bytes(pair)


def set_battle_palette(item: ModItem, palette: int) -> None:
    """A weapon's (or shield's) palette in battle (0 to 15), its picture and its second palette as they were."""
    if item.kind in (WEAPON, SHIELD) and len(item.sprite_pair) == PAIR_BYTES:
        palette = max(0, min(int(palette), PALETTES - 1))
        item.sprite_pair = bytes([(palette << 4) | (item.sprite_pair[0] & 0x0F), item.sprite_pair[1]])


def looks_of(game: "GameItems", category: int) -> list:
    """The game's weapons a weapon of `category` may look like in battle (`battle_family`), or (5 November) its
    shields, for a shield (category 19), each its number and its sprite pair, in their numbers' order."""
    family = battle_family(category)
    out = []
    for number in GAME_ITEMS:
        made = game.item(number)
        if made.kind in (WEAPON, SHIELD) and made.record[CATEGORY_AT] in family \
                and len(made.sprite_pair) == PAIR_BYTES:
            out.append((number, bytes(made.sprite_pair)))
    return out


def swing_palettes(game: "GameItems") -> tuple:
    """The palettes the game's own weapons swing in (their sprite pairs' high four bits), in order: what
    `SWING_PALETTES` was measured from."""
    found = set()
    for number in GAME_ITEMS:
        made = game.item(number)
        if made.kind == WEAPON and len(made.sprite_pair) == PAIR_BYTES:
            found.add(made.sprite_pair[0] >> 4)
    return tuple(sorted(found))


def guard_palettes(game: "GameItems") -> tuple:
    """The palettes the game's own shields guard in (their sprite pairs' high four bits), in order."""
    found = set()
    for number in GAME_ITEMS:
        made = game.item(number)
        if made.kind == SHIELD and len(made.sprite_pair) == PAIR_BYTES:
            found.add(made.sprite_pair[0] >> 4)
    return tuple(sorted(found))


def look_now(looks: list, pair: bytes) -> int:
    """Which of `looks` a sprite pair draws as (the same picture and second palette, its palette the same first), or
    0 when none does."""
    same = [n for n, p in looks if p[1] == pair[1] and (p[0] & 0x0F) == (pair[0] & 0x0F)]
    exact = [n for n in same if dict(looks)[n] == pair]
    return (exact or same or [0])[0]


def look_groups(looks: list) -> list:
    """
    (Zodi, 4 November: "many of them share the same design so what you get
    is a lot of repeating looks in the list with different item names") The
    looks a weapon may swing, each picture once: `[[the game's weapons]]`
    whose sprite pairs draw the same picture. The swing draws its picture
    from the pair's second byte alone (its row on the weapons' texture, in
    the type's column) and colors it by its first byte's high four bits;
    the low four bits, a second palette, color only the swing's effects
    (fft_decomp's `sprite_thrown_item_palette_set`: the item's palettes go
    to its unit's ITEM_A row, which the weapon's block draws with, and
    ITEM_B, the effect blocks'). So a picture is a row: the knives' 10 are
    4, the swords' family's 55 are 14, measured in his program. Each list
    in its weapons' order, the lists in their first weapons' order.
    """
    rows = {}
    for number, pair in looks:
        if len(pair) == PAIR_BYTES:
            rows.setdefault(pair[1], []).append(number)
    return sorted(rows.values(), key=lambda group: group[0])


def look_group(looks: list, pair: bytes) -> list:
    """The game's weapons of `looks` whose look draws the picture `pair` draws (the same row, `look_groups`), in their
    order; [] when none does."""
    if len(pair) != PAIR_BYTES:
        return []
    return [n for n, p in looks if len(p) == PAIR_BYTES and p[1] == pair[1]]


# =============================================================================
# (1.28.0) The game's own weapons' looks in battle (Zodi, 3 November, after test 60: "apply our item's sprite pair
# findings to the Items page on the Mod Studio so that users can also change the vanilla items look and palette")
# =============================================================================

#: A mod's looks for the game's own weapons: one file at the mod's root, read by Mod Studio Framework as the game
#: starts (`ItemLooks.cs`), which writes each look where the game's own ItemSpritePair finds that item's (the game keeps
#: its weapons' sprite pairs in its program, not in a table the mod loader changes).
LOOKS_FILE = "ModStudioItemLooks.json"
LOOKS_FORMAT = "Mod Studio item looks"
LOOKS_VERSION = 1


def looks_text(looks: dict) -> str:
    """The looks' file for `{item: its sprite pair}` (the helper's `ItemLooks`), in the items' order, each list of
    bytes on one line."""
    out = {"Format": LOOKS_FORMAT, "Version": LOOKS_VERSION,
           "Looks": [{"Item": int(n), "SpritePair": list(bytes(looks[n]))} for n in sorted(looks)]}
    text = json.dumps(out, indent=2, ensure_ascii=False)
    return re.sub(r"\[\s+([\d,\s]+?)\s+\]", lambda m: "[" + " ".join(m.group(1).split()) + "]", text) + "\n"


def read_looks_text(text: str) -> tuple:
    """(`{item: its sprite pair}`, problems) from a looks' file's text, as the helper reads it (`ItemLooks.Read`): the
    whole file refused for a problem of its own, a look with a problem of its own left out, each said in the helper's
    words."""
    try:
        top = hj.loads(text)
    except ValueError as exc:
        return {}, [f"it isn't JSON ({exc})"]
    if not isinstance(top, dict):
        return {}, ["it isn't a list of fields"]
    if hj.get(top, "Format") != LOOKS_FORMAT:
        return {}, [f"its Format isn't \"{LOOKS_FORMAT}\""]
    version = hj.get(top, "Version")
    if not _whole(version) or version != LOOKS_VERSION:
        return {}, [f"its Version is {_raw(top, 'Version')}, not {LOOKS_VERSION}"]
    listed = hj.get(top, "Looks")
    if not isinstance(listed, list):
        return {}, [f"its Looks is a list of the game's items' looks, not {_raw(top, 'Looks')}"]
    looks, problems = {}, []
    for n, entry in enumerate(listed, 1):
        if not isinstance(entry, dict):
            problems.append(f"its look {n} isn't a list of fields (its Item and its SpritePair)")
            continue
        item = hj.get(entry, "Item")
        if not _whole(item) or item not in GAME_ITEMS:
            problems.append(f"its look {n}'s Item is one of the game's items (1 to 253, or 256 to {MOST_GAME_ITEM}), "
                            f"not {_raw(entry, 'Item')}")
            continue
        pair = _bytes(entry, "SpritePair", PAIR_BYTES)
        if pair is None:
            problems.append(f"its look {n}'s SpritePair is a sprite pair's two bytes (each 0 to 255), not "
                            f"{_raw(entry, 'SpritePair')}")
            continue
        if item in looks:
            problems.append(f"its look {n} is for item {item} again")
            continue
        looks[item] = pair
    return looks, problems


def read_looks(mod_root) -> tuple:
    """A mod's looks for the game's weapons (`LOOKS_FILE` at its root), read as the helper reads them: ({}, []) when it
    has none."""
    path = Path(mod_root) / LOOKS_FILE
    if not path.is_file():
        return {}, []
    try:
        text = hj.read_text(path)
    except OSError as exc:
        return {}, [f"it can't be read ({exc})"]
    return read_looks_text(text)


def write_looks(mod_root, looks: dict) -> list:
    """The looks' file written into the mod (or taken away when it has none). Returns the paths written."""
    path = Path(mod_root) / LOOKS_FILE
    if not looks:
        if path.is_file():
            path.unlink()
        return []
    path.write_text(looks_text(looks), encoding="utf-8")
    return [LOOKS_FILE]


def game_look(game: "GameItems", number: int) -> bytes:
    """A game weapon's or (5 November) shield's own sprite pair as its program has it (b"" for any other)."""
    made = game.item(number)
    return bytes(made.sprite_pair) if made.kind in (WEAPON, SHIELD) and len(made.sprite_pair) == PAIR_BYTES else b""


def look_with_palette(pair: bytes, palette: int) -> bytes:
    """A sprite pair with another palette (0 to 15), its look's row and its second palette as they were."""
    palette = max(0, min(int(palette), PALETTES - 1))
    return bytes([(palette << 4) | (pair[0] & 0x0F), pair[1]])
