"""
Nenkai's `.layout` files, read as the source of truth about `.nxd` tables.

    https://github.com/Nenkai/fftivc-nex-layouts
    bundled from 335747ed6453b2386f7fada2db66f956ebd56c35, MIT

### Why this exists

Mod Studio has been carrying its own answers to questions the layouts
already answer, written out by hand, one list per page. Four separate
lists of "which columns of this table are per-language text" existed:
`NxdTableSpec.text_fields`, `PoachingPage.COPY_SKIP_FIELDS`,
`AbilitiesPage.COPY_SKIP_FIELDS` and `encounters.CHARA_TEXT_FIELDS`.

Two of the four were wrong, and one of them destroys data. Checked
against the layouts, then against the real 1.5.2 database:

- `PoachItem` has six string columns. Poaching's list named six columns
  too - but five of the six it named (`Name`, `NameSingular`,
  `NamePlural`, `Name2`, `Description`) **do not exist in that table**,
  and five that do (`Unknown8`, `UnknownC`, `Unknown10`, `Unknown14`,
  `Unknown18`) were left out. All 96 rows of all five differ between
  every pair of languages, so they are unambiguously translations -
  `Unknown18` holds the carcass descriptions. "Copy to other languages"
  therefore overwrote the Japanese, French and German text with English.
- `Ability.Unknown10` is a string and was likewise unprotected.

The lists were not sloppily written; they were copied from a table that
happened to have those columns and then reused for tables that do not.
That is what a hand-maintained restatement of someone else's schema does
over time, and it is why this module reads the schema instead.

### What a layout carries

    table_name|JobCommand
    set_table_type|SingleKeyed
    set_table_category|SingleKeyed_Localized
    add_column|Name|string|rel
    add_column|Description|string|rel|-4
    add_column|Unknown14|int

Enough to build a table's whole identity: its sqlite table prefix
(`JobCommand-en`), its filename stem (`jobcommand.en.nxd`), whether it is
per-language at all (`_Localized`), every column, and every column's type.

53 of the 245 bundled layouts are `Localized`. Mod Studio has curated tabs
for six of them.
"""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

#: `add_column|Name|string|rel|-4    // trailing comment`
#: The type is the third field; anything after it is addressing detail
#: this does not need. Comments can follow any of it.
_COLUMN = re.compile(
    r"^add_column\|([^|\n]+)\|([^|\n/]+?)(?:\|[^\n/]*)?\s*(?://.*)?$", re.M)
_SETTING = re.compile(r"^(\w+)\|(.+?)\s*(?://.*)?$", re.M)


def layout_dir() -> Path:
    """`data/nex_layouts`, which ships in frozen builds."""
    from . import paths
    return Path(paths.bundled_data_dir()) / "nex_layouts"


def layout_files() -> dict:
    """
    `{filename: path}`, a fetched copy of a layout beating the bundled one.

    Per file, so "Check for updates" pulling one changed layout replaces
    exactly that layout. See `upstream.py` for why downloads land outside
    `data/` rather than over it.
    """
    from . import upstream
    return upstream.resolve("nex_layouts", ".layout")


class NxdLayout:
    """One parsed `.layout` file."""

    def __init__(self, path: Path):
        self.path = Path(path)
        source = self.path.read_text(encoding="utf-8", errors="replace")
        settings = {k: v.strip() for k, v in _SETTING.findall(source)
                    if k not in ("add_column",)}
        self.table_name = settings.get("table_name", self.path.stem).strip()
        self.table_type = settings.get("set_table_type", "")
        self.category = settings.get("set_table_category", "")
        self.columns = [(name.strip(), kind.strip())
                        for name, kind in _COLUMN.findall(source)]

    @property
    def localized(self) -> bool:
        """Whether the game ships one file per language for this table."""
        return "Localized" in self.category

    @property
    def nxd_stem(self) -> str:
        """`JobCommand` -> `jobcommand`, giving `jobcommand.en.nxd`."""
        return self.table_name.lower()

    @property
    def string_columns(self) -> tuple:
        """
        The columns holding text, and therefore holding TRANSLATIONS.

        This is the answer the four hand-written lists were trying to
        give. A string column of a localized table is per-language by
        definition, so it must never be copied from one language to
        another - that is not a judgement call anyone needs to make per
        page, it is a property of the column.
        """
        return tuple(name for name, kind in self.columns if kind == "string")

    def column_names(self) -> tuple:
        return tuple(name for name, _kind in self.columns)

    def __repr__(self) -> str:
        return (f"<NxdLayout {self.table_name} "
                f"{'localized' if self.localized else 'shared'} "
                f"{len(self.columns)} columns>")


@lru_cache(maxsize=1)
def all_layouts() -> dict:
    """
    Every bundled layout, by table name.

    Cached, because it is read on the way into several pages and parsing
    245 small files on every call would be paid for repeatedly and
    silently. `lru_cache` rather than a module global so a test can clear
    it.
    """
    found = {}
    for _name, path in sorted(layout_files().items()):
        try:
            layout = NxdLayout(path)
        except Exception:                                     # noqa: BLE001
            continue
        if layout.table_name:
            found[layout.table_name] = layout
    return found


def layout_for(table_name: str):
    """One layout by its table name, or None if it is not bundled."""
    return all_layouts().get(table_name)


def localized_layouts() -> dict:
    """Only the per-language tables - the ones with a file per language."""
    return {name: layout for name, layout in all_layouts().items()
            if layout.localized}


def translated_columns(table_name: str, fallback=()) -> tuple:
    """
    The columns of `table_name` that hold translations.

    `fallback` is returned when the layout is not bundled, so a caller
    that already had a hand-written list is never left with an EMPTY skip
    list - which would silently turn "copy the shared fields" into "copy
    everything, including the translations". Failing back to the old
    answer is imperfect; failing back to nothing is destructive.
    """
    layout = layout_for(table_name)
    if layout is None:
        return tuple(fallback)
    return layout.string_columns
