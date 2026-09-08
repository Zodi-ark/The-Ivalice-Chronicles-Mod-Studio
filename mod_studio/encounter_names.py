"""
Human-readable names for encounters (the Key half of OverrideEntryData).

The problem this solves: the Encounters tab listed rows as "Encounter 460",
which tells a user nothing about which battle they're editing. It now reads
"Encounter 460 - Chapter 4 - Mullonde Cathedral".

Names come from data/EncounterNames.txt, a plain "id|name" list that ships
populated from FFTPatcher's ENTD event names and can be edited freely. See
NOTICE.md for the licensing, which is the reason Mod Studio is GPL-3.0.

Two things deliberately NOT done here:

- **No hex anywhere in the UI.** FFTPatcher lists these ids in hex, so an
  earlier version showed "Encounter 460 (0x1CC)" to make cross-referencing
  easy. With real names shipped, that cross-reference is no longer the
  point, and hex in front of a basic user is just noise. parse_encounter_id
  still ACCEPTS hex typed into the "Go to" box, since someone arriving from
  FFTPatcher may have a hex id in hand and it costs nothing - it's just not
  advertised in the tab.
- **No reading of the game's own EntryNo table.** That looked promising -
  EntryNo is keyed by the same entry numbers and has a Comment column - but
  Zodi checked a real entryno.nxd and the Comment column is empty for every
  entry. The code that read it has been removed rather than left in as a
  path that can never fire.
"""
from __future__ import annotations

from pathlib import Path

from . import constants as c
from . import paths

NAMES_FILE_HEADER = """\
# Encounter names for The Ivalice Chronicles Mod Studio
# =====================================================
#
# One encounter per line:
#
#     <decimal id>|<name>
#
# Blank lines and lines starting with # are ignored. Ids are DECIMAL,
# matching what the .nxd files and this tool use. If you are copying from a
# source that lists them in hex (FFTPatcher does), convert first - the
# Encounters tab shows both, so "Encounter 460 (0x1CC)" is the same battle
# FFTPatcher calls 1CC.
#
# Example:
#
#     460|Chapter 4 - Mullonde Cathedral
#
# This file ships EMPTY on purpose. The most complete public list of what
# each entry number corresponds to is FFTPatcher's ENTD tab, and FFTPatcher
# is licensed GPL-3.0 - so redistributing its list inside this tool is a
# licensing decision for whoever publishes Mod Studio, not something the
# tool should do on its own. Filling this file in for your own use is
# entirely your business; sharing a filled-in copy is between you and the
# source you took it from.
#
"""


def names_file_path() -> Path:
    return paths.bundled_data_dir() / "EncounterNames.txt"


def load_names_file(path: Path | None = None) -> dict:
    """
    {encounter_id: name} from the user's names file. Missing file, blank
    file, and malformed lines are all non-events - this is a nicety, and it
    should never be the reason the Encounters tab fails to open.
    """
    path = path or names_file_path()
    names: dict = {}
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return names
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, sep, value = line.partition("|")
        if not sep:
            continue
        value = value.strip()
        if not value:
            # "99|" with nothing after it is not a name. Skipping keeps the
            # loaded count honest and avoids labels ending in a stray dash.
            continue
        try:
            names[int(key.strip(), 0)] = value
        except ValueError:
            continue
    return names


class EncounterNames:
    """Resolves an encounter id to a display label, from whatever sources are available."""

    def __init__(self, names: dict | None = None):
        self.names = names or {}

    @classmethod
    def load(cls) -> "EncounterNames":
        return cls(load_names_file())

    @property
    def source_count(self) -> int:
        return len(self.names)

    def name_for(self, encounter_id: int):
        return self.names.get(encounter_id) or None

    def label_for(self, encounter_id: int) -> str:
        """
        "460 Chapter 4 - Mullonde Cathedral", or just "460" when the id
        isn't named.

        No "Encounter" prefix and no dash between the number and the name:
        everything in this list is an encounter, so the word adds nothing,
        and the names themselves already contain a dash ("Chapter 4 -
        Mullonde Cathedral"). Together they produced "Encounter 460 -
        Chapter 4 - Mullonde Cathedral", which reads as three things
        separated by two dashes.
        """
        name = self.name_for(encounter_id)
        return f"{encounter_id} {name}" if name else str(encounter_id)

    def describe_sources(self) -> str:
        if not self.names:
            return (
                "No encounter names loaded - data/EncounterNames.txt is missing or empty, "
                "so encounters are listed by number only."
            )
        return f"{len(self.names)} encounter names loaded from data/EncounterNames.txt."


def parse_encounter_id(text: str):
    """
    Accepts "460", "0x1CC" and bare "1CC" - the last because someone
    reading a battle out of FFTPatcher will have a hex number in front of
    them and no reason to think about prefixes. Returns None if it isn't a
    number in either base.

    Ambiguity is resolved in favour of decimal: "460" is 460, not 0x460.
    Bare hex only kicks in when the text can't be decimal at all (it
    contains A-F), so "1CC" is unambiguous while "460" stays decimal.
    """
    text = (text or "").strip()
    if not text:
        return None
    try:
        return int(text, 10)
    except ValueError:
        pass
    candidate = text[2:] if text.lower().startswith("0x") else text
    try:
        return int(candidate, 16)
    except ValueError:
        return None


def ensure_names_file(path: Path | None = None) -> Path:
    """Creates the (empty, header-only) names file if it isn't there yet."""
    path = path or names_file_path()
    if not path.exists():
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(NAMES_FILE_HEADER, encoding="utf-8")
        except OSError:
            pass
    return path
