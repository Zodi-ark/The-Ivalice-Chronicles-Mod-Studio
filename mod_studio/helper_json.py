"""
A mod's JSON files (its quests', places', roads' and quest maps') read as
Mod Studio Framework reads them, so Mod Studio says what the helper will
say of a file, word for word (1.10.0).

- **The text** (`read_text`): as .NET's `File.ReadAllText` gives it: a byte
  order mark says the encoding (UTF-8, UTF-16 or UTF-32, either order) and
  is dropped; without one, UTF-8; bytes that aren't text become U+FFFD
  rather than stopping the read.
- **The JSON** (`loads`): as System.Text.Json's `JsonDocument.Parse`: `NaN`
  and `Infinity` aren't JSON. A field named twice is kept twice
  (`Fields.pairs`, in order), as the helper sees every field; looked up
  without case, the first one counts (`get`, `has`).
- **Its texts** (`broken_text`): a `\\u` escape of half a surrogate pair
  alone is no text to the helper (System.Text.Json can't read it as one),
  so a file holding one anywhere, in a field's name or its value, is
  refused whole (`BROKEN_TEXT`).

Nothing here imports Qt.
"""
from __future__ import annotations

import json
import unicodedata
from pathlib import Path

#: What a file holding half a surrogate pair alone is told, after "its <file> ".
BROKEN_TEXT = "has a text that isn't Unicode text (half of a surrogate pair alone)"
#: Byte order marks, as .NET looks for them (UTF-32's little-endian before UTF-16's).
_MARKS = ((b"\xef\xbb\xbf", "utf-8"), (b"\xff\xfe\x00\x00", "utf-32-le"), (b"\x00\x00\xfe\xff", "utf-32-be"),
          (b"\xff\xfe", "utf-16-le"), (b"\xfe\xff", "utf-16-be"))


def read_text(path) -> str:
    """A file's text as `File.ReadAllText` reads it (see the module's notes). OSError when it can't be read."""
    data = Path(path).read_bytes()
    for mark, encoding in _MARKS:
        if data.startswith(mark):
            return data[len(mark):].decode(encoding, errors="replace")
    return data.decode("utf-8", errors="replace")


class Fields(dict):
    """A JSON object: a dict (a field named twice holds its last value), with every field in order in `pairs`."""

    def __init__(self, pairs):
        super().__init__(pairs)
        self.pairs = list(pairs)


def pairs(d: dict) -> list:
    """Every field of a JSON object in order, one named twice twice."""
    return d.pairs if isinstance(d, Fields) else list(d.items())


def _refuse(constant: str):
    raise ValueError(f"{constant} isn't JSON")


def loads(text: str):
    """The JSON in `text`, its objects `Fields`; ValueError for what isn't JSON to the helper."""
    return json.loads(text, object_pairs_hook=Fields, parse_constant=_refuse)


def get(d: dict, name: str, default=None):
    """A field by its name without case: the first so named, as the helper reads them."""
    for key, value in pairs(d):
        if key.lower() == name.lower():
            return value
    return default


def has(d: dict, name: str) -> bool:
    return any(key.lower() == name.lower() for key, _ in pairs(d))


def units(text: str) -> int:
    """A text's length as the helper counts it: in UTF-16 units (a character past U+FFFF two)."""
    return len(text.encode("utf-16-le")) // 2


def good_name(name) -> bool:
    """
    A name as the helper takes one (`QuestFile.GoodName`: a quest's, its
    flags', events' and battles', a quest map's folder's): 1 to 64 UTF-16
    units, each a letter (any of Unicode's letter categories), a decimal
    digit, a space, _ or -, with no space at either end. A character past
    U+FFFF is two units to the helper, neither a letter.
    """
    return (isinstance(name, str) and 0 < len(name) <= 64 and name.strip() == name
            and all(ord(c) <= 0xFFFF and (c.isalpha() or unicodedata.category(c) == "Nd" or c in " _-")
                    for c in name))


def _broken(text: str) -> bool:
    return any(0xD800 <= ord(c) <= 0xDFFF for c in text)


def broken_text(value) -> bool:
    """Whether a text in `value` (a field's name or a value, at any depth) holds half a surrogate pair alone."""
    if isinstance(value, str):
        return _broken(value)
    if isinstance(value, dict):
        return any(_broken(key) or broken_text(item) for key, item in pairs(value))
    if isinstance(value, list):
        return any(broken_text(item) for item in value)
    return False
